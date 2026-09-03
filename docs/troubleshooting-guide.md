# Troubleshooting Guide — IntelliGrade v1.0

Common problems and their fixes, organized by when you'd hit them. For
production incidents (elevated errors, outages), see
`docs/incident-response-guide.md` instead — this document is for
installation/development/day-to-day usage problems.

## Installation problems

**`OCR provider 'tesseract' is not registered` / OCR jobs stay `failed`**
Tesseract isn't installed, or `TESSERACT_CMD` (Windows) doesn't point at
the real binary. Confirm with `tesseract --version` on the command line;
if that works but the app still can't find it, check `TESSERACT_CMD` in
`backend/.env`.

**`connection refused` on backend startup (database)**
PostgreSQL isn't running, or `POSTGRES_HOST`/`POSTGRES_PORT` in
`backend/.env` don't match your actual setup. Confirm with
`pg_isready -h <host> -p <port>`.

**`Address already in use` on `docker compose up` / `uvicorn`**
Something else is already using port 8000/5173/5432/6379/9000. Either
stop the conflicting process or change the port in `.env`/`docker-compose.yml`.

**`npm install` fails / frontend won't start**
Confirm Node.js 20+ (`node --version`). This project uses npm workspaces
— run `npm install` from the **repository root**, not `frontend/`
directly, so the workspace lockfile resolves correctly.

**`npm run build` or `npm run typecheck` fails**
As of v1.0 this should be clean on a fresh checkout. If you see a
TypeScript error in a file you didn't touch, check
`KNOWN_LIMITATIONS.md` for any currently-known pre-existing issue before
assuming you broke something.

## Development problems

**Tests fail with a database-related error**
The backend test suite uses an isolated, in-memory SQLite database per
test (via `conftest.py`'s `db_engine` fixture) — it does not touch your
real configured PostgreSQL at all. A database-related test failure is
almost never "my local Postgres is misconfigured"; look at the actual
error message.

**"Slow query" warnings flooding my logs in local dev**
`SLOW_QUERY_THRESHOLD_MS` defaults to 200ms — a local dev machine under
load (or a cold-cache first request) can legitimately cross that. Not a
bug; raise the threshold locally if it's noisy, or investigate the
flagged statement if it's consistently slow.

**Rate limited (429) constantly during local testing**
`SlowAPIMiddleware` enforces `RATE_LIMIT_DEFAULT` (100/minute) globally
as of v1.0 — a test script hammering the API in a tight loop will hit
this. Either slow down your test script or raise `RATE_LIMIT_DEFAULT`
locally (never in production).

## Usage problems (for administrators/teachers)

**"I can't see an institution/exam/student that I know exists"**
Almost always a missing `UserInstitution` membership — the requesting
user needs an active membership row for that institution (unless they're
`super_admin`). See `docs/administrator-manual.md`.

**"I can't unlock a result"**
`exam_results:unlock` is deliberately withheld from the default teacher
grant (ADR-042) — this requires `institution_admin` or `super_admin`.
Not a bug.

**"The AI evaluation seems wrong"**
Check whether the official Model Answer/Mark Scheme were actually
**verified** (not just OCR'd) before evaluation ran — unverified extracted
content can contain OCR errors that propagate into the evaluation. Fix
the verified content and use **Rerun** (not a plain re-evaluate) to force
recomputation.

**"My report never finished generating"**
Report generation runs via Celery in the background — if no Celery
worker is running (common in a minimal local dev setup), the job stays
`pending` indefinitely rather than failing outright (a deliberate
best-effort design, not silently broken). Start a worker: `celery -A
app.tasks.celery_app worker --loglevel=info`.

**"A form won't let me submit / shows a generic error"**
As documented in `KNOWN_LIMITATIONS.md`, most CRUD forms in v1.0 rely on
server-side validation surfaced as a toast, without inline per-field
errors. Check the toast message for the actual validation reason (e.g. a
field that's too long, a duplicate code) — it's usually specific even
though it's not shown inline.

## Still stuck?

- Check `KNOWN_LIMITATIONS.md` — your issue may be a documented,
  known gap rather than a new bug.
- Check `docs/runbook.md`'s "Where to look when something's wrong" table
  if this is a running-deployment issue rather than local usage.
- For anything infrastructure/deployment-related, `docs/operations-manual.md`
  is the index into the right guide.
