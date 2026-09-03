# Quality Gate — Module 01 Foundation Audit

**Date:** 2026-07-15
**Scope:** Full repository audit and hardening pass, per the enterprise
quality-gate mandate. No business logic, authentication, OCR, or AI
features were added — this pass verified and hardened Module 01's existing
foundation only.
**Method:** Read every backend and frontend module, every config file,
every Docker/CI file, and every doc. Ran the actual toolchain (pip, npm,
pytest, vitest, black, ruff, isort, eslint, prettier, tsc) rather than
inspecting code statically only. Where a finding was non-obvious, verified
it empirically (see "Verification method" notes below) rather than
asserting it from code-reading alone.

## Executive summary

Found and fixed **3 critical bugs** that would have blocked real usage of
this foundation, plus **~15 hardening issues** (silent failure modes,
dead/misleading code, an accessibility failure, documentation drift).
**All fixes are verified — either via automated tests or direct empirical
reproduction — not just asserted.** Zero regressions: every pre-existing
test still passes, plus 22 new tests were added covering the fixed code.

**Verdict: ✅ APPROVED FOR MODULE 02**

## Critical findings (would have blocked real usage)

### 1. Password hashing was completely non-functional

`passlib[bcrypt]` 1.7.4 (unmaintained since 2020) is incompatible with
`bcrypt` >= 4.1 (the version that `pip install` resolves today). Every
call to `hash_password()` raised `ValueError: password cannot be longer
than 72 bytes` — even for short passwords — because passlib's internal
bcrypt-version self-test itself fails first.

**Verification method:** Ran `hash_password()` directly in the installed
venv; reproduced the crash with a full traceback before fixing.

**Fix:** Replaced `passlib` with direct `bcrypt` library usage in
`app/core/security.py`. Added 6 regression tests (`tests/test_security.py`)
covering hash/verify round-trip, wrong-password rejection, and the 72-byte
limit (now a clean `ValueError` instead of silent truncation).

### 2. The frontend Docker image could not build

`frontend/Dockerfile` used a `./frontend` build context, but this is an
npm-workspaces monorepo — `package-lock.json` lives at the repo root,
outside that context, and Docker cannot see files outside its build
context. `npm ci` would have had no lockfile to install from.

**Verification method:** No Docker daemon is available in this audit
environment, so `docker build` itself could not be run. Instead,
reproduced each Dockerfile stage's exact command sequence in an isolated
directory containing only the files that build context would actually
contain (confirmed this fails pre-fix, then confirmed the fixed version
succeeds, including that `frontend/dist` lands at the exact path the
production stage's `COPY --from=build` expects, and that Node's module
resolution correctly finds `node_modules` from the `frontend/` working
directory).

**Fix:** Changed the frontend build to use repo-root context
(`docker-compose.yml`, `.github/workflows/docker.yml`,
`frontend/Dockerfile` all updated), added a root `.dockerignore`, removed
the now-dead `frontend/.dockerignore`.

### 3. That same fix would have hit a second wall: the root `prepare` script

Once building with `npm ci --workspace=frontend` (required for the fix
above), a second failure surfaced: npm always runs the root package's
`prepare` script during `npm ci`, regardless of `--workspace` scoping.
`"prepare": "husky"` fails when husky itself isn't part of the scoped
install (it's a root-only devDependency) — aborting the entire install.

**Verification method:** Reproduced this failure directly (captured the
exact npm error), then verified the fix (`"prepare": "husky || true"`,
Husky's own documented remedy for this scenario) resolves it while
confirming normal local installs still initialize husky's git hooks
correctly.

## Hardening findings (silent failure modes, not outright breakage)

All of the following were found, fixed, and covered by a new regression
test unless noted otherwise. Full detail in [CHANGELOG.md](CHANGELOG.md).

- Validation-error responses could crash with `TypeError` instead of
  returning a clean 422 (raw Pydantic error `ctx` isn't always
  JSON-serializable) — confirmed the crash reproduces pre-fix via a
  minimal validator, confirmed the fix (`jsonable_encoder`) resolves it.
- Structured JSON logging had no fallback serializer — one bad log call
  could have crashed the entire logging pipeline. Added `default=str`.
- Request ID was captured but never bound into structlog's `contextvars`,
  so log lines outside the access-log middleware carried no request ID
  despite the processor chain being built to support it. Fixed and
  verified end-to-end (a log line from a real request now provably carries
  the client-supplied request ID).
- `/health/ready` checked Postgres and Redis sequentially; now concurrent
  via `asyncio.gather` (halves probe latency).
- DB/Redis health-check failures were silently swallowed; now logged.
- No fail-fast check existed for booting in production with a placeholder
  or weak `SECRET_KEY`. Added, tested against both known placeholders and
  a length heuristic.
- Rate limiting's `default_limits` was configured but never enforced (no
  `SlowAPIMiddleware` registered) — investigated whether to wire it up
  globally, and deliberately chose not to: doing so would have coupled
  `/health*` probes to Redis availability, and `slowapi` has a real quirk
  where a Redis outage during a limit check gets misreported as
  `RateLimitExceeded` rather than an infrastructure failure. Documented
  this as an explicit decision (ADR-005), not left as a silent gap.
- Frontend: `src/api/health.ts` violated this repo's own documented rule
  (raw `import.meta.env` read instead of the validated `env` object) and
  used a fragile regex to derive a URL; both fixed.
- **Accessibility (WCAG failure):** collapsed sidebar nav links were
  icon-only with the label conditionally unmounted — no accessible name at
  all for screen readers. Fixed (title attribute + `sr-only` label kept in
  DOM); added a regression test that was confirmed to fail against the
  original code and pass against the fix. Also added a "skip to main
  content" link.
- Dead configuration: root `package.json` listed `shared` as an npm
  workspace member despite it having no `package.json` — npm silently
  dropped it. Removed to match reality (ADR-004).
- Misleading migration docstring claimed `pgcrypto` was used for
  database-side UUID generation; the actual mixin generates UUIDs
  application-side. Corrected (ADR-002).
- Minor DRY/KISS cleanups: a pointless pass-through dependency wrapper in
  `app/api/deps.py`, a trivial one-line helper function in
  `app/core/rbac.py`, a local import that should have been module-level in
  `app/db/session.py`.

## Scores

| Category | Score | Rationale |
|---|---:|---|
| Architecture | 92/100 | Clean layering verified end-to-end, no circular imports or hidden coupling found. Deducted for the still-undecided multi-tenancy model and one dead-config item found (now fixed). |
| Code Quality | 90/100 | black/ruff/isort/eslint/prettier/tsc all clean. Deducted for the volume of dead code, misleading comments, and silent-failure patterns found — real issues, now fixed, but their presence reflects room for improvement in the original pass. |
| Security | 85/100 | A critical, complete failure of password hashing was found and fixed — severe in nature (would have blocked Module 02 on day one), but caught before any real endpoint used it. Everything else in the security foundation checked out clean. See [SECURITY_CHECKLIST.md](SECURITY_CHECKLIST.md). |
| Documentation | 95/100 | Comprehensive prior set, one stale command found and fixed, now supplemented with a full governance doc set. |
| Testing | 82/100 | Backend coverage 67% → 76%, previously-untested security-critical modules now at 100%. Playwright e2e not re-executed this pass (see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)); `mypy` blocked by a local environment policy. |
| Scalability | 85/100 | Async DB pooling, UUID PKs, modular-monolith extraction path, Celery/MinIO groundwork all sound. Multi-tenancy model still an open decision. |
| Maintainability | 92/100 | Strong conventions, DRY after fixes, governance docs now in place for long-term continuity. |
| Production Readiness | 78/100 | Correctly *not* production-ready as a product (no auth — by design), but the foundation itself is now solid. Deducted for: Docker build verified by simulation rather than an actual `docker build` (no daemon available here), `mypy` unverified locally, and rate limiting intentionally inert. |

## Repository statistics

- **Folders:** 75 (excluding `node_modules`, `.venv`, `.git`, build caches)
- **Files:** ~172 tracked-relevant files (same exclusions) before this
  pass; see additions/modifications below
- **Files added this pass:** 16 — 9 governance docs (this file and its
  8 siblings), 5 new backend test files (`test_security.py`,
  `test_config.py`, `test_exceptions.py`, `test_logging.py`,
  `test_middleware.py`), 1 new frontend test file (`Sidebar.test.tsx`),
  1 new root `.dockerignore`
- **Files modified this pass:** ~22 — `app/core/security.py`,
  `app/core/exceptions.py`, `app/core/logging.py`, `app/core/config.py`,
  `app/core/rbac.py`, `app/middleware/request_id.py`,
  `app/middleware/logging_middleware.py`, `app/middleware/rate_limit.py`,
  `app/api/deps.py`, `app/api/health.py`, `app/db/session.py`,
  `app/db/redis.py`, `backend/pyproject.toml`,
  `backend/alembic/versions/0001_initial_baseline.py`,
  `frontend/src/api/health.ts`, `frontend/src/components/layout/Sidebar.tsx`,
  `frontend/src/layouts/DashboardLayout.tsx`, `frontend/src/App.tsx`
  (Suspense wiring, carried over from prior session), root `package.json`,
  `docker-compose.yml`, `frontend/Dockerfile`,
  `.github/workflows/docker.yml`, `docs/deployment-guide.md`
- **Files removed this pass:** 1 — `frontend/.dockerignore` (superseded by
  the new root `.dockerignore`, since the frontend build context changed)

## Technical debt identified (tracked, not all fixed — by design)

See [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) for the full list with
reasoning. Highlights: multi-tenancy model undecided; rate limiting
inert-by-design pending a real endpoint to protect; `mypy` unverified in
this environment; Docker build verified by simulation, not a live build;
color-contrast accessibility not visually audited.

## Risks

1. **Docker build unverified via actual `docker build`.** High confidence
   from manual reproduction of every stage's commands, but not a
   substitute for a real build. *Mitigation:* run `docker compose up -d
   --build` on a machine with Docker before the next deployment-adjacent
   milestone.
2. **`mypy` has never successfully run against this codebase** in any
   session so far (blocked in this environment both times). Type hints are
   present throughout and `tsc`/pyright-adjacent tooling (IDE diagnostics
   surfaced during editing) caught nothing, but static type-checking
   coverage is unconfirmed. *Mitigation:* run `mypy app` on an unrestricted
   machine before Module 02 lands significant new typed code.
3. **The severity of the password-hashing bug suggests dependency pinning
   discipline should tighten.** `passlib[bcrypt]>=1.7.4` allowed pip to
   resolve an incompatible `bcrypt` transitively with no warning until
   runtime. *Mitigation:* the fix removes the risky dependency entirely;
   going forward, consider `pip-audit` or Dependabot in CI to catch this
   class of issue earlier.

## Recommendations before Module 02

1. Run `docker compose up -d --build` on a Docker-capable machine to give
   the fixed build configuration a real (not simulated) verification pass.
2. Run `mypy app` on a machine without this sandbox's Application Control
   restriction.
3. Decide the multi-tenancy model (see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md))
   before Module 02 designs the first Institution/User tables — it shapes
   every repository query pattern that follows.
4. When Module 02 adds the first protected endpoint, follow the pattern
   already documented in `app/middleware/rate_limit.py`'s docstring:
   register `SlowAPIMiddleware` and `@limiter.exempt` the health checks in
   the same change, not as an afterthought.

## Final verdict

**✅ APPROVED FOR MODULE 02.**

All critical issues found during this audit have been fixed and verified
— not merely patched, but confirmed correct via automated tests or direct
empirical reproduction of both the failure and the fix. No regressions:
26/26 backend tests pass, 8/8 frontend unit tests pass, both apps boot and
serve traffic correctly (verified live, including a real headless-browser
session against the frontend talking to a live backend). The foundation is
solid enough to build Module 02 on.
