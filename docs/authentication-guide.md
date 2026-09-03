# Authentication Guide

Module 02 implements the full authentication flow described here. This
document is the reference for how login, token issuance, refresh, and
logout actually work — read it before touching `app/services/auth_service.py`,
`app/services/token_service.py`, or the frontend `api/client.ts` interceptors.

## Token model

Two tokens, two lifetimes, two storage locations:

| Token | Lifetime | Where it lives | Why |
|---|---|---|---|
| **Access token** (JWT) | `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30) | In-memory only — Redux `auth` slice | Never touches disk or `localStorage`; an XSS payload that runs JS can still read it, but it evaporates on tab close/reload and isn't handed to every same-site subdomain the way a cookie would be. |
| **Refresh token** | `REFRESH_TOKEN_EXPIRE_DAYS` (default 7, `REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS` default 30 with "remember me") | httpOnly, `SameSite=Lax`, path-scoped cookie (`path=/api/v1/auth`) | Never readable by JS at all (mitigates XSS token theft). Path-scoped so the browser only attaches it to auth endpoints, not e.g. `/api/v1/users` — reduces exposure and keeps the cookie out of unrelated request logs. |

The access token carries `sub` (user id), `roles`, and `family_id` (see
below) as claims. It is **not** persisted server-side — validity is purely
cryptographic (HS256 signature + expiry), so revocation only takes effect at
refresh time, not mid-lifetime. Keep `ACCESS_TOKEN_EXPIRE_MINUTES` short for
this reason.

The refresh token is a high-entropy opaque string
(`app.core.security.generate_opaque_token`), **hashed with SHA-256 before
storage** (`app.core.security.hash_token`) in the `refresh_tokens` table —
the raw token is shown to the client exactly once (in the Set-Cookie header)
and never persisted in retrievable form, the same principle applied to
password-reset tokens.

## Refresh token rotation and family-based reuse detection

Every successful `/auth/refresh` call:
1. Validates the presented refresh token against its stored hash and
   `expires_at`.
2. **Revokes it** and issues a brand-new refresh token + access token pair.
3. The new refresh token is linked to the same `family_id` (a UUID assigned
   at login and carried through every rotation in that session's lineage).

If a refresh token is presented that has *already been rotated* (i.e. its
`revoked_at` is set but someone still has the old value — the classic sign
of a stolen, cached, or replayed token), `TokenService.rotate_refresh_token`
treats this as a **reuse event**: it revokes the *entire token family*
immediately, forcing every device on that session lineage to re-authenticate.
This is the OWASP-recommended mitigation for refresh token theft — a stolen
token is only useful once before it burns down the whole session.

This is why `family_id` also rides along in the **access token**, not just
the refresh cookie: the sessions list (`GET /sessions`) needs to mark which
session is "this one," but the refresh cookie is path-scoped to
`/api/v1/auth` and never reaches `/api/v1/sessions` — so `is_current` is
computed by comparing `CurrentUser.session_family_id` (decoded from the
access token) against each session's `refresh_token_family_id`, not by
reading a cookie the browser wouldn't have sent anyway.

## Commit-before-raise: why failed logins are still recorded

A subtlety that caused a real bug during this module's implementation:
FastAPI's session-per-request pattern rolls back the DB session when an
exception propagates out of the request. If `auth_service.login()` raised
`InvalidCredentialsError` immediately after incrementing
`failed_login_count`, the increment was silently undone by the rollback —
the lockout counter never actually advanced no matter how many times a
wrong password was submitted.

Fix: `auth_service.py` and `token_service.py` explicitly call
`await self.session.commit()` **before** raising on every failure path that
follows a state-changing write (failed-login counter, lockout timestamp,
audit log entry, family revocation on reuse detection). This is documented
in `auth_service.py`'s module docstring — any new failure path added to
that service must follow the same pattern or its audit trail will silently
disappear.

## Login flow

```
POST /api/v1/auth/login  { identifier, password, remember_me }
  → AuthService.login()
      1. Look up user by email or username.
      2. If account is locked (locked_until in the future) → 423 AccountLockedError.
      3. Verify password. On failure:
         - increment failed_login_count
         - if failed_login_count >= MAX_FAILED_LOGIN_ATTEMPTS → set locked_until
         - commit, write an audit log entry (LOGIN_FAILED), then raise 401
      4. On success: reset failed_login_count to 0, update last_login_at.
      5. Issue a token pair (new family_id), start a Session record, write
         an audit log entry (LOGIN).
      6. Set the refresh-token cookie; return { access_token, user } in the body.
```

Rate limited at `10/minute` per IP (`@limiter.limit("10/minute")`) to slow
down credential-stuffing without needing per-account lockout to carry the
entire burden.

## Logout

```
POST /api/v1/auth/logout
  → revokes the current refresh token's entire family
  → revokes the matching Session record
  → clears the refresh-token cookie
  → audit log entry (LOGOUT)
```

Logging out revokes the whole family, not just the one refresh token — this
also invalidates any already-rotated-but-unused tokens in that lineage,
closing the same window a reuse attack would otherwise exploit.

## Password change / reset

- **Change password** (`POST /auth/change-password`, authenticated):
  requires the current password, validates the new one against
  `password_policy.py`, rejects reuse against `password_history`
  (`PASSWORD_HISTORY_LIMIT`, default last 5 hashes), and — because a
  password change is a strong signal of compromise-recovery intent —
  revokes every refresh token family for that user, forcing re-login on all
  other devices.
- **Forgot / reset password**: `POST /auth/forgot-password` always returns
  a generic 202 message regardless of whether the email is registered
  (prevents user enumeration). If registered, a single-use, hashed,
  time-boxed (`PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`) token is generated and
  would be emailed (no email provider is wired in Module 02 — the token
  issuance/validation path is complete and tested, delivery is a Module 03+
  concern). `POST /auth/reset-password` validates the token, applies the
  same policy/reuse checks as change-password, and revokes all sessions.

Both endpoints are rate-limited (`5/minute` on forgot-password) since they
are unauthenticated and otherwise abusable.

## Account lockout

`User.is_locked` compares `locked_until` (made timezone-aware via
`ensure_aware()` — SQLite returns naive datetimes even from
`DateTime(timezone=True)` columns, which is not exclusively a SQLite
concern; any driver that doesn't guarantee tz-aware round-trips would hit
the same comparison bug) against "now." Configurable via
`MAX_FAILED_LOGIN_ATTEMPTS` and `ACCOUNT_LOCKOUT_DURATION_MINUTES`.

## Frontend integration

- `context/AuthProvider.tsx` calls `POST /auth/refresh` silently on mount to
  restore a session from the httpOnly cookie (no access token survives a
  page reload otherwise, by design).
- `api/client.ts`'s response interceptor catches a `401`, triggers a single
  shared in-flight refresh call (de-duplicated via a module-level
  `refreshPromise` so N concurrent 401s don't fire N refresh requests),
  retries the original request once (`_retry` flag), and — if the refresh
  itself fails — clears Redux credentials and redirects to `/login`.
  `NO_REFRESH_RETRY_PATHS` excludes the auth endpoints themselves from this
  loop to avoid infinite recursion on a genuinely bad login attempt.
- Route guards (`routes/guards/ProtectedRoute.tsx`,
  `RoleGuard.tsx`, `PermissionGuard.tsx`) read `auth.status` /
  `auth.user` from Redux and redirect to `/login` or `/unauthorized`
  accordingly — see [rbac.md](rbac.md) for the authorization side.
