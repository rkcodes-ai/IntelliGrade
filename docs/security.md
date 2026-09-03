# Security Foundation

Module 01 established security **primitives**. Module 02 wires them into a
complete authentication/authorization flow. This document describes what's
in place today; see [authentication-guide.md](authentication-guide.md) and
[rbac.md](rbac.md) for the full design rationale.

## What exists today

### Password hashing
`app.core.security.hash_password` / `verify_password` — `bcrypt` called
directly (see ADR-006). Domain code should never hash passwords itself.
`app.core.password_policy` enforces minimum length (8), an upper bound (72
— bcrypt's own input limit, checked explicitly rather than silently
truncated), and requires uppercase/lowercase/digit/special-character
classes. `PasswordService.assert_not_reused` additionally checks the new
password against `password_history` (last `PASSWORD_HISTORY_LIMIT` hashes,
default 5) via `bcrypt` verify, not a reversible comparison.

### JWT primitives and issuance
`app.core.security.create_token` / `decode_token` sign/verify JWTs using
`SECRET_KEY` + `JWT_ALGORITHM` (HS256 by default). `TokenService` is the
only caller that issues real tokens: `create_access_token(user, roles, *,
family_id)` for short-lived (`ACCESS_TOKEN_EXPIRE_MINUTES`) bearer tokens,
and opaque, SHA-256-hashed-at-rest refresh tokens for
`REFRESH_TOKEN_EXPIRE_DAYS` (or `REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS`).
Refresh tokens rotate on every use and use family-based reuse detection —
presenting an already-rotated token revokes the entire session family. Full
detail in [authentication-guide.md](authentication-guide.md).

### Account lockout
`ACCOUNT_LOCKOUT_MAX_ATTEMPTS` failed logins within the tracked window locks
the account for `ACCOUNT_LOCKOUT_DURATION_MINUTES`
(`User.is_locked`/`locked_until`). The failed-login counter survives the
exception path via an explicit commit before the 401 is raised — see the
"commit-before-raise" section of the authentication guide; without it, a
DB-session rollback on the exception path would silently erase the counter
increment.

### RBAC — implemented
`app.core.rbac.CurrentUser` resolves a user's roles and permissions from
the database (not hardcoded) via `get_current_user`, which decodes and
validates the bearer JWT. `require_roles(*roles)` and
`require_permissions(*codes)` are FastAPI dependencies applied to every
protected endpoint — no endpoint rolls its own authorization check. Full
model in [rbac.md](rbac.md).

### Audit logging
`AuditService`/`AuditLogRepository` write an append-only record for every
security-relevant event (login, logout, failed login, password
change/reset, profile update, role change, session revocation), each
capturing user, timestamp, IP, user agent, and request ID (correlated with
`RequestIDMiddleware`). See
[database-standards.md](database-standards.md#audit-log-shape).

### Rate limiting
`app.middleware.rate_limit` wires `slowapi` (Redis-backed, in-memory
fallback) with a global default (`RATE_LIMIT_DEFAULT`, default
`100/minute`). Auth endpoints now apply tighter, endpoint-specific limits:
`10/minute` on `/auth/login`, `5/minute` on `/auth/forgot-password` — both
unauthenticated and otherwise abusable for credential stuffing / enumeration.
As of Module 08, `SlowAPIMiddleware` is registered in `app/main.py`, so the
global default is actually enforced on *every* route, not just the
explicitly-decorated auth endpoints — the 3 health-probe endpoints
(`/health`, `/health/live`, `/health/ready`) are marked `@limiter.exempt` so
load balancers/orchestrators polling them frequently are never throttled.

### CORS
Configured via `CORS_ORIGINS` in `app.core.config.Settings`, applied in
`app/main.py`. Defaults to the local Vite dev server origin only — add
staging/production frontend origins via the environment, never widen to `*`
with `allow_credentials=True` (that combination is a CORS misconfiguration
that defeats the same-origin protection entirely).

### Security headers
`app.middleware.security_headers` sets `X-Content-Type-Options`,
`X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` on every
response. Extend this, don't replace it, when adding CSP once frontend
asset hashing strategy is finalized.

### Secrets
Never committed. `.env` files are gitignored; `.env.example` files document
required variables with placeholder values (see
[environment-guide.md](environment-guide.md)). `SECRET_KEY` has an
obviously-insecure default (`dev-only-insecure-secret-change-me`) so it's
impossible to accidentally deploy with it unnoticed — `Settings.is_production`
should gate a startup check in a future module that refuses to boot with
the default key set.

## CSRF strategy — implemented

Access tokens travel as `Authorization: Bearer` headers, not cookies —
CSRF exploits the browser's *automatic* cookie attachment, which doesn't
apply to a header an attacker's cross-origin page can't set. This alone
protects every endpoint except the refresh cookie itself.

The refresh token **is** a cookie (httpOnly, required so JS — including an
XSS payload — can never read it). Its CSRF exposure is mitigated by three
layers, all currently in place:
- `SameSite=Lax` — blocks the cookie from being attached to cross-site
  `POST` requests (the CSRF-relevant case) while still allowing normal
  top-level navigation.
- `path=/api/v1/auth` — the cookie is never attached to any other route,
  shrinking the attack surface to just the four auth endpoints that read it.
- CORS is configured with an explicit origin allow-list
  (`CORS_ORIGINS`), never `*` with `allow_credentials=True` — a
  cross-origin page cannot complete a fetch/XHR against the API even if it
  could somehow trigger the cookie's attachment.

A double-submit CSRF token was evaluated and deemed unnecessary given the
above three layers combined with `SameSite=Lax` on a same-site-only
deployment; revisit if a future module needs to support authenticated
cross-origin embeds (e.g. an LTI iframe integration), which would force
`SameSite=None` and reopen this gap.

## Production hardening (Module 08)

Everything above this section is application-level security and remains
unchanged. Module 08 adds an infrastructure-level hardening layer on top,
without touching any business logic:

- **TLS termination** at the `nginx` reverse proxy (`nginx/conf.d/`), not
  the application — HSTS + security headers applied at the edge for every
  response, TLS 1.2/1.3 only.
- **Non-root containers**: backend, worker, and frontend production images
  all run as an unprivileged user (`appuser` / `nginx-unprivileged`'s
  built-in non-root user).
- **Network segmentation**: `edge` vs `internal` Docker networks
  (`docker-compose.prod.yml`) — postgres/redis/minio are unreachable except
  from the backend/worker containers, even if the frontend or nginx were
  compromised.
- **Secrets management**: real secrets live only in an untracked
  `.env.production` (gitignored); `.env.production.example` ships
  placeholder values that are obviously not usable as-is.
- **Automated scanning**: `.github/workflows/security.yml` runs secret
  scanning (gitleaks), dependency scanning (pip-audit, npm audit), and
  container image scanning (Trivy) on every push/PR plus a weekly sweep.
  `.github/dependabot.yml` opens update PRs for pip/npm/docker/GitHub
  Actions dependencies.
- **Bounded health-check timeouts**: `DATABASE_CONNECT_TIMEOUT_SECONDS` /
  `REDIS_CONNECT_TIMEOUT_SECONDS` (both default 3s) bound how long
  `/health/ready` can take when a dependency is actually down — discovered
  via a real load test where the probe took ~4.1s per call with no bound,
  cutting it close against the 5s Docker healthcheck timeout.

See `SECURITY_CHECKLIST.md`'s Module 08 addendum for the full OWASP Top 10
walkthrough, and `docs/production-checklist.md` for the pre-launch checklist.

## Threat model notes for future modules

- **File uploads** (answer scripts, images for OCR) must validate content
  type and size server-side before touching MinIO, not trust the client
  `Content-Type` header.
- **Multi-tenancy** (multiple institutions) requires every query in a
  repository to filter by institution/tenant ID once that model exists —
  a missing tenant filter is a data-leak bug, not just a bug.
- **AI/LLM inputs** (once the AI module lands): treat OCR'd text as
  untrusted input to any prompt — prompt-injection from a student's answer
  script is a realistic threat for an AI grading system.
