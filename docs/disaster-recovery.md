# Disaster Recovery (Module 08)

## Scope

Full-loss scenarios: the host running the production stack is destroyed,
corrupted beyond repair, or its data volumes are lost/unrecoverable. For
smaller incidents (one bad deploy, one bad migration), see
`docs/rollback-guide.md` and `docs/incident-response-guide.md` instead —
this document is for "start over from backups on a new host."

## Recovery objectives

These targets are a direct function of the backup cadence in
`docs/backup-guide.md`, not an independently-chosen SLA — tighten the
backup schedule first if a tighter RPO is needed.

| Metric | Target | Basis |
|---|---|---|
| **RPO** (Recovery Point Objective) | ≤ 24 hours | Daily backup cadence recommended in `docs/backup-guide.md`. Reduce by scheduling `backup-postgres.sh`/`backup-minio.sh` more frequently (e.g. every 4–6 hours) if a tighter RPO is required — the scripts themselves impose no minimum interval. |
| **RTO** (Recovery Time Objective) | ≤ 2 hours | Estimated: provision a new host (~30 min), restore Postgres (~15 min for a small-to-medium dataset via `restore-postgres.sh`), restore MinIO (~30 min, depends on object volume), bring the stack up and smoke-test (~15 min). **Not yet empirically measured against a real multi-GB dataset** — treat as a planning estimate until a real DR drill validates it (see below). |

## Full recovery procedure

1. **Provision a new host** with Docker + Docker Compose installed.
2. **Clone the repository** (or restore it from your own source control /
   artifact mirror) onto the new host.
3. **Recreate `.env.production`** from your secrets manager/vault — this
   file is never in a backup (it's gitignored and contains live secrets,
   deliberately not archived alongside application data).
4. **Bring up only the data services** first, so restores target an empty,
   healthy Postgres/MinIO rather than a partially-started app stack:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.production up -d postgres redis minio
   ```
5. **Restore Postgres**:
   ```bash
   scripts/backup/restore-postgres.sh <path-to-latest-backup>.sql.gz --yes
   docker compose -f docker-compose.prod.yml --env-file .env.production run --rm backend alembic upgrade head
   ```
   (Run any migrations applied *after* the backup was taken — the restore
   only brings back data as of the backup point, not schema changes made
   since.)
6. **Restore MinIO**:
   ```bash
   scripts/backup/restore-minio.sh <path-to-latest-snapshot-dir>
   ```
7. **Bring up the rest of the stack**:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
   ```
8. **Verify**: `/health/ready` reports `ready`; spot-check that recently
   ingested data before the disaster (that would be lost per the RPO) is
   understood and communicated to stakeholders — anything created after
   the last backup is genuinely gone.
9. **Point DNS/load balancer** at the new host once verification passes.

## What is NOT recoverable

- Anything written between the last successful backup and the moment of
  loss (bounded by your actual RPO — see above).
- Redis contents (Celery queue state, rate-limit counters) — not backed up
  by design (ephemeral, reconstructable). In-flight Celery tasks at the
  time of loss will need to be identified and manually re-triggered from
  the backend's own records (e.g. any OCR/evaluation job whose result never
  landed).
- Anything in `.env.production` if it is not separately held in a secrets
  manager — losing the host without a secrets-manager copy means
  regenerating `SECRET_KEY` (invalidates all active JWTs — every user must
  log in again) and rotating all other credentials.

## DR drill recommendation

The RTO above is an estimate, not a measured result — this sandbox has no
real multi-GB Postgres/MinIO dataset or second host to drill against.
Schedule a real DR drill (restore onto a genuinely separate host, from a
real backup, timed end-to-end) at least once before treating the RTO above
as reliable, and after any significant change to the backup/restore
scripts or data volume.
