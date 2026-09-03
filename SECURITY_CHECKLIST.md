# Security Checklist

Tracks security posture against `docs/security.md`'s stated foundation.
Updated for Module 02 completion (2026-07-16). Module 01's original
findings remain valid and are folded into the table below where superseded.
Re-review this checklist at the end of every future module.

## Authentication & session security (Module 02)

| Item | Status | Notes |
|---|---|---|
| Password hashing | ✅ Verified | Direct `bcrypt` usage (ADR-006), 72-byte input explicitly rejected rather than silently truncated. |
| Password policy | ✅ Enforced | Min 8 chars, upper/lower/digit/special-char classes, checked both server-side (`password_policy.py`) and client-side (zod schema mirroring it). |
| Password reuse prevention | ✅ Enforced | Last `PASSWORD_HISTORY_LIMIT` (5) hashes compared via `bcrypt` verify on every change/reset. |
| Account lockout | ✅ Enforced | `ACCOUNT_LOCKOUT_MAX_ATTEMPTS` failed logins locks for `ACCOUNT_LOCKOUT_DURATION_MINUTES`; counter survives the exception path via explicit commit-before-raise (ADR-012). |
| JWT access tokens | ✅ Verified | Short-lived (`ACCESS_TOKEN_EXPIRE_MINUTES`), in-memory-only storage (Redux, never `localStorage`), HS256, tampering rejected (full-4-char-group corruption tested to avoid a base64-padding false negative). |
| Refresh token storage | ✅ Verified | Opaque, SHA-256-hashed at rest, httpOnly + `SameSite=Lax` + path-scoped (`/api/v1/auth`) cookie — never JS-readable, never in the response body (ADR-010). |
| Refresh token rotation | ✅ Verified | Every refresh revokes-and-reissues; reuse of an already-rotated token revokes the entire family (ADR-011). |
| CSRF strategy | ✅ Implemented | Bearer-header access tokens are immune by construction; the one cookie in the system is `SameSite=Lax` + path-scoped + origin-allowlisted CORS. See `docs/security.md`. |
| RBAC | ✅ Implemented | `require_roles`/`require_permissions` on every protected endpoint, backed by real DB-driven role/permission resolution (`docs/rbac.md`). No endpoint hand-rolls an authorization check. |
| Rate limiting | ✅ Enforced on auth endpoints | `10/minute` on login, `5/minute` on forgot-password; global default (`100/minute`) elsewhere. Supersedes the Module 01 "configured, not enforced" finding (ADR-005) for these routes. |
| Audit logging | ✅ Implemented | Append-only trail for 9 action types, each with user/timestamp/IP/user-agent/request-id. Endpoints never write `audit_logs` directly — only through `AuditService`. |
| Anti-enumeration | ✅ Verified | `/auth/forgot-password` returns an identical response whether or not the email is registered. |
| Input validation | ✅ Verified | Pydantic v2 schemas reject unknown fields; carried forward from Module 01. |
| Error exposure | ✅ Verified | Unhandled exceptions return a generic message; carried forward from Module 01. |
| Secrets committed to git | ✅ Verified clean | No IAM-related secrets (JWT keys, seed data) committed; `.env.example` uses placeholder values only. |

## Dependency-level findings

Carried forward from Module 01 — no new dependency-level issues found
during Module 02 (`passlib[bcrypt]` already removed; no other
passlib-class incompatibilities across the newly-added `slowapi` usage
paths).

## Not yet applicable (Module 03+ scope)

- Multi-tenant data isolation — no tenant/institution model exists yet.
- File upload validation (content-type/size checks before MinIO) — no
  upload endpoints exist yet.
- Prompt-injection defenses for AI evaluation input — no AI module exists yet.
- Email delivery for password-reset tokens — token issuance/validation is
  complete and tested; the transport (SMTP/SES/etc.) is deferred.

## Verdict (Module 02)

Authentication, RBAC, session, and audit-logging security are correct,
tested (87 backend / 79 frontend tests, including a dedicated
`test_security_hardening.py`), and safe to build on. No committed secrets,
no broken cryptography, no unenforced auth-adjacent rate limits.
**Approved as a base for Module 03.**

---

## Module 08 addendum — Production Hardening (2026-07-22)

Modules 01–07 business logic and the table above are **frozen** and
unchanged by this addendum — everything below is production/infrastructure
hardening only, mapped against OWASP Top 10 (2021).

| # | Category | Status | Notes |
|---|---|---|---|
| A01 | Broken Access Control | ✅ Unchanged (frozen) | RBAC (`require_roles`/`require_permissions`) untouched. New network segmentation (`edge`/`internal` Docker networks in `docker-compose.prod.yml`) adds a second, infra-level access-control layer: postgres/redis/minio/worker have no route from the public edge even if application-level auth were somehow bypassed. |
| A02 | Cryptographic Failures | ✅ Hardened | TLS now terminates at the `nginx` reverse proxy (`nginx/conf.d/intelligrade.conf`, TLS 1.2/1.3 only, HSTS); self-signed cert for this sandbox (see `nginx/certs/README.md` for real-CA/certbot guidance before real production use). `SECRET_KEY`/`POSTGRES_PASSWORD`/`REDIS_PASSWORD`/`MINIO_ROOT_PASSWORD` are all `REPLACE_ME_*` placeholders in `.env.production.example` forcing a real per-deployment value; Redis now requires a password in production (`--requirepass`, not optional as in dev). |
| A03 | Injection | ✅ Unchanged (frozen) | SQLAlchemy parameterized queries, Pydantic validation — no code path touched. |
| A04 | Insecure Design | ✅ Hardened | `SlowAPIMiddleware` is now registered (`app/main.py`), enforcing `RATE_LIMIT_DEFAULT` globally on every route except the 3 `@limiter.exempt` health probes — previously only the explicitly-decorated auth endpoints were enforced (ADR-005's original gap). Real-load verification: see the load-test results in the Module 08 report — `/openapi.json` genuinely returned `429` under concurrent load, confirming the middleware is live, not just configured. |
| A05 | Security Misconfiguration | ✅ Hardened | All 3 runtime images (backend, worker, frontend) run as non-root; production/worker images no longer ship a compiler toolchain (`runtime-base` vs `build-base` split in `backend/Dockerfile`); `/metrics` is explicitly blocked at the public edge (`deny all; return 404;` in nginx) — only reachable from Prometheus on the internal Docker network; `.env.production` stays gitignored, only `.env.production.example` is tracked (verified via `git check-ignore`/`git add --dry-run`). |
| A06 | Vulnerable and Outdated Components | ✅ Hardened | `.github/dependabot.yml` covers `pip`, `npm`, `docker` (backend + frontend separately), and `github-actions`, weekly. `.github/workflows/security.yml` adds `pip-audit` (backend), `npm audit` (frontend), and Trivy container scanning (backend + frontend production images) on every push/PR plus a weekly scheduled sweep. |
| A07 | Identification and Authentication Failures | ✅ Unchanged (frozen) | JWT issuance/rotation, lockout, password policy untouched — see the Module 02 table above. |
| A08 | Software and Data Integrity Failures | ✅ Hardened | `.github/workflows/deploy.yml` publishes images to GHCR tagged by branch, semver, and full commit SHA (not just a mutable `latest`), so a deployed image is always traceable to an exact commit. `.github/workflows/security.yml`'s gitleaks job scans full git history on every run, catching a committed secret before it can be built into an image. |
| A09 | Security Logging and Monitoring Failures | ✅ Hardened | New `/metrics` endpoint (`prometheus-fastapi-instrumentator`) + Prometheus + Grafana (`docker-compose.monitoring.yml`) give real request-rate/error-rate/latency visibility that didn't exist before Module 08. New slow-query logging (`SLOW_QUERY_THRESHOLD_MS`, `app/db/session.py`) surfaces DB performance problems as structured `slow_query` log events. Existing structured JSON logging, request-ID correlation, and the audit-log trail (all frozen, Module 01/02) remain the source of truth for security-relevant events. |
| A10 | Server-Side Request Forgery (SSRF) | ✅ Verified, not applicable | No current endpoint accepts a user-supplied URL for the server to fetch (OCR/report generation operate on internally-referenced MinIO object keys, never arbitrary URLs) — no code change made. Re-check this row if a future module adds URL-based ingestion (e.g. "import from a link"). |

### CORS / CSRF / JWT re-review (unchanged, re-confirmed)

No code changes were made to auth flows — modifying them would cross into
frozen business logic. Re-reviewed and re-confirmed still sound:

- **CORS**: origin allow-list via `CORS_ORIGINS`, never `*` with
  `allow_credentials=True`. `.env.production.example` documents setting it
  to the real public domain only.
- **CSRF**: unchanged three-layer mitigation (bearer-header access tokens
  immune by construction; `SameSite=Lax` + path-scoped refresh cookie +
  origin-allowlisted CORS) — see `docs/security.md`. No dedicated CSRF
  token was added; the existing mitigation remains defensible for a
  same-site-only JSON API deployment topology (which the new reverse-proxy
  design reinforces, since the frontend and API are now always same-origin
  in production — see `VITE_API_BASE_URL=/api/v1` in
  `.env.production.example`).
- **JWT**: HS256, `SECRET_KEY` sourced from environment only, no default
  ever shipped in a production env file (placeholder forces a real value).

### Known gaps carried forward honestly (not fixed in this module)

- No CSP (Content-Security-Policy) header yet — flagged in `docs/security.md`
  since Module 02 as pending frontend asset-hashing strategy; still true.
- No WAF / DDoS-mitigation layer in front of nginx — out of scope for a
  single-host reverse-proxy deployment; note in `docs/production-checklist.md`
  if fronting with a cloud LB/CDN.
- TLS certificate shipped in this repo's `nginx/certs/` is self-signed
  (sandbox has no real domain to obtain a CA-signed cert for) — replace
  with a real certificate (certbot/ACME or your CA of choice) before
  exposing this to real traffic; see `nginx/certs/README.md`.

---

## Module 09 addendum — v1.0 Release Certification Audit (2026-07-23)

An independent security audit re-verified every claim in this document
against the current code (not just re-reading the doc) ahead of v1.0
certification. **Every previously-documented control held up under direct
inspection** — JWT issuance/rotation, DB-driven RBAC, the restrictive
student-default permission philosophy, `SlowAPIMiddleware`'s global
rate-limit enforcement, non-root Docker images, `edge`/`internal` network
segmentation, and security headers (including nginx-layer HSTS/TLS 1.2+)
were all independently confirmed true, not just asserted.

Two real, previously-undocumented gaps were found and are now tracked in
`KNOWN_LIMITATIONS.md`'s Module 09 section (both judged Medium, not
Critical — neither blocks v1.0):

- **`npm audit`**: 7 real CVEs (2 critical, 2 high, 3 moderate) in
  frontend **devDependencies** (`vite`/`vitest`/`esbuild`/`fast-uri`) —
  confined to build/test tooling, zero production-bundle impact.
  `pip-audit` reports zero backend vulnerabilities.
- **File-upload content-type validation** (Module 05/06) trusts the
  client-supplied `Content-Type` header rather than sniffing file bytes —
  this row was previously marked "Not yet applicable (Module 03+ scope)"
  in the table above, which was **stale** now that real upload endpoints
  exist. Corrected here rather than silently left wrong.

Two stale doc/code-comment mismatches were also found and fixed as part
of this module: `backend/app/middleware/rate_limit.py`'s docstring still
described `SlowAPIMiddleware` as unregistered (pre-Module-08 language,
contradicted by the actual code since Module 08); and this document
previously referenced a non-existent setting name
(`MAX_FAILED_LOGIN_ATTEMPTS` — the real field is
`ACCOUNT_LOCKOUT_MAX_ATTEMPTS`). Both are corrected above.

One genuine, release-blocking **bug** (not a security issue) was found in
the same audit pass and fixed: a route-registration-order defect in
`exam_results.py` made all 3 bulk exam-result actions
(`/bulk/approve|lock|publish`) unreachable via the API. See
`CHANGELOG.md`'s `[0.9.0]` entry for detail — noted here because it was
found during the same comprehensive audit, not because it was itself a
security defect.

**Verdict: security posture is certified sound for v1.0**, with the two
Medium findings above tracked as accepted, non-blocking risk for a
future module to address.

---

## Module 10 addendum — Live Deployment Validation correction (2026-07-23)

**Correction to the Module 08/09 rate-limiting claim above.** Both this
document's Module 08 addendum and the Module 09 audit stated that
`SlowAPIMiddleware` genuinely enforces `RATE_LIMIT_DEFAULT` globally, and
verified this as true at the time — correctly, based on the code and the
FastAPI version installed during those passes.

Module 10's live deployment validation found, by actually hammering a
running instance of the app with 100+ rapid requests to an undecorated
route, that this had gone **silently non-functional**: dependency drift
(an unpinned `fastapi>=0.115.0` constraint resolving to `0.139.0`)
introduced a FastAPI-internal route-wrapping optimization
(`_IncludedRouter`) that `slowapi`'s middleware route-lookup cannot see
through, causing every route without its own explicit
`@limiter.limit(...)`/`@limiter.exempt` decorator to be silently treated
as exempt from the global default. **Fixed** — see
`KNOWN_LIMITATIONS.md`'s Module 10 section for the full root-cause and
fix detail, and `tests/test_security_hardening.py::
test_default_rate_limit_applies_to_undecorated_routes` for the permanent
regression test.

**Lesson recorded, not just the fix**: this class of defect — a security
control that silently degrades due to an unrelated dependency version
change, invisible to the existing test suite because no test exercised
any single route near the configured limit — is exactly what live,
load-style validation catches and pure code review does not. Recommend
this exact check (hammer a real undecorated route past `RATE_LIMIT_DEFAULT`
and confirm a 429 appears) become a standing item in any future
pre-release validation pass, not a one-time audit artifact.

**Verdict, updated**: the global rate-limiting control is now verified
working via the new, FastAPI-version-independent implementation, and is
backed by a regression test the previous implementation never had.
