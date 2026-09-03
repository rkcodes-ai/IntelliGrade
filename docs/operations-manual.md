# Operations Manual — IntelliGrade v1.0

The single entry point for running IntelliGrade day-to-day in production.
This document is an index/overview; each linked guide has the full
detail — don't duplicate their content here, read them.

## What you're operating

IntelliGrade is a modular-monolith FastAPI + React application running as
7 Docker Compose services (`postgres`, `redis`, `minio`, `backend`,
`worker`, `frontend`, `nginx`) behind a TLS-terminating reverse proxy,
with an optional Prometheus + Grafana monitoring overlay. See
`docs/architecture.md` for the full design and `docs/deployment-guide.md`
for how the pieces fit together.

## Daily operations

| Task | Where to look |
|---|---|
| Start/stop the stack, check service health, tail logs, scale the worker | `docs/runbook.md` |
| Read dashboards, understand what `/metrics` exposes, add a panel | `docs/monitoring-guide.md` |
| Run a backup, verify one is restorable | `docs/backup-guide.md` |
| Roll out a new release | `docs/upgrade-guide.md` |
| Something just broke after a deploy | `docs/rollback-guide.md` |

## When something goes wrong

1. Start with `docs/incident-response-guide.md` — severity triage and
   the first things to check for each severity level.
2. If it's a specific symptom (502s, slow API, elevated errors), `docs/
   runbook.md`'s "Where to look when something's wrong" table maps
   symptoms to likely causes.
3. If it's a user-reported issue rather than an alert, `docs/
   troubleshooting-guide.md` covers common user-facing problems and their
   fixes.
4. If it's total data loss, `docs/disaster-recovery.md`.

## Weekly/monthly cadence

- **Daily**: automated backups (`scripts/backup/backup-postgres.sh`/
  `backup-minio.sh`, scheduled per `docs/backup-guide.md`).
- **Weekly**: `.github/workflows/security.yml`'s scheduled scan runs
  automatically; review any new findings in the Security tab.
  `.github/dependabot.yml` opens weekly dependency-update PRs — review
  and merge them promptly, don't let them pile up.
- **Monthly**: test-restore the most recent backup against a non-
  production target (`docs/backup-guide.md`'s verification section) —
  an unverified backup is not a real backup.
- **Quarterly (recommended, not yet automated)**: rotate `SECRET_KEY`
  and database/Redis/MinIO credentials; run a real DR drill
  (`docs/disaster-recovery.md`).

## Who to involve

This manual assumes a small operations team without a dedicated on-call
rotation. For anything beyond a routine restart:

- **Application-level bugs/errors**: whoever maintains the codebase (see
  `docs/contributing.md`).
- **Data/RBAC/institution setup questions**: `docs/administrator-manual.md`
  — most "how do I..." questions about running an institution are
  answered there, not here.
- **Infrastructure/deployment changes**: whoever owns
  `docker-compose.prod.yml`/`nginx/`/CI — treat changes to these the same
  as application code changes (review, test, `docs/upgrade-guide.md`'s
  procedure).

## Key facts worth memorizing

- Only `nginx` publishes host ports — every other service is reachable
  only from other containers on the same Docker network.
- `/metrics` is deliberately blocked at the public edge; Prometheus
  reaches the backend directly on the internal network.
- The backend refuses to boot in production with a placeholder
  `SECRET_KEY` — a real fail-fast safety net, not a bug if you see it.
- Redis requires a password in production (`docker-compose.prod.yml`
  sets `--requirepass`), unlike local dev.
- `DATABASE_CONNECT_TIMEOUT_SECONDS`/`REDIS_CONNECT_TIMEOUT_SECONDS`
  (3s default) bound how long `/health/ready` can take when a dependency
  is down — don't raise these without also raising the Docker healthcheck
  timeout that depends on them staying under it.
