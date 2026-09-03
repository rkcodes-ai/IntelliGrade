# Incident Response Guide (Module 08)

## Severity levels

| Level | Definition | Example |
|---|---|---|
| SEV-1 | Full outage or data-integrity risk | Backend down, database unreachable, data corruption suspected |
| SEV-2 | Significant degradation, partial functionality lost | Elevated 5xx rate, Celery worker down (async jobs queuing but not processing), one dependency (MinIO) unreachable |
| SEV-3 | Minor degradation, workaround exists | Elevated latency within tolerable bounds, non-critical endpoint slow |

## Immediate triage (any severity)

1. Check `/health/ready` and `docker compose -f docker-compose.prod.yml ps`
   — which container(s) are unhealthy?
2. Check the Grafana overview dashboard (`docs/monitoring-guide.md`) —
   is this a request-rate spike, an error-rate spike, or a latency
   regression? These point to different root causes (capacity vs. bug vs.
   dependency).
3. Check `docker compose logs -f <service>` for the affected service —
   look for the actual exception, not just "it's down."
4. Consult `docs/runbook.md`'s "Where to look when something's wrong" table
   for the specific symptom.

## SEV-1: full outage

1. Confirm scope: is it the reverse proxy (nginx down/misconfigured),
   the backend, or a data dependency (Postgres/Redis/MinIO)?
2. If a bad deploy is the suspected cause (recent `deploy.yml` run,
   recent `docker compose ... up -d` on this host): follow
   `docs/rollback-guide.md` immediately — don't debug forward under
   pressure when a known-good previous image is one command away.
3. If a data dependency is down and won't recover
   (`docker compose restart postgres` doesn't help): check the container's
   own logs for a corruption/disk-space signal before assuming application
   code is at fault.
4. If this is genuine data loss (not just a down container): follow
   `docs/disaster-recovery.md`.
5. Once mitigated, write up what happened (see "Post-incident" below)
   before considering the incident closed.

## SEV-2: significant degradation

1. Elevated 5xx: check backend logs for the actual exception; check
   whether it correlates with a specific handler in the Grafana error-rate
   panel (points at one endpoint/feature vs. systemic).
2. Celery worker down: `docker compose logs worker`; confirm the container
   is even running (`docker compose ps`); confirm expected task names are
   registered (`celery -A app.tasks.celery_app inspect registered` inside
   the container) — a missing `include` entry in `celery_app.py` is a real
   class of bug this module fixed once already (Celery registers tasks
   fine in the API process because it imports task modules directly to
   call `.delay()`, which masks an incomplete `include` list until an
   actual standalone worker runs).
3. One dependency unreachable (e.g. MinIO down but Postgres/Redis fine):
   `/health/ready` only checks DB+Redis today, not MinIO — a MinIO outage
   won't flip readiness to `not_ready`. Check MinIO's own container health
   directly; file-upload/report-generation endpoints will fail even though
   `/health/ready` still reports `ready`. (Flagged as a known gap — see
   `KNOWN_LIMITATIONS.md`.)

## SEV-3: minor degradation

1. Check the Grafana p95/p99 latency panel and backend logs for
   `slow_query` events — a query crossing `SLOW_QUERY_THRESHOLD_MS`
   (default 200ms) is logged with the statement text, which usually points
   directly at the cause.
2. If load-related (rate limiting kicking in, i.e. elevated 429s): this
   may be expected behavior under a real traffic spike, not a bug — see
   `RATE_LIMIT_DEFAULT` sizing guidance in `docs/production-checklist.md`.

## Post-incident

For SEV-1 and SEV-2 incidents, write a short retro covering: what
happened, when it was detected, time to mitigation, root cause, and one
concrete follow-up action (a code fix, a new alert, a doc update). Keep it
short — a retro nobody reads is worse than no retro. Fold any resulting
doc/runbook gap directly into `docs/runbook.md` or this file so the next
on-call benefits from it.
