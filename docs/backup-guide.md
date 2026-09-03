# Backup Guide (Module 08)

## What's backed up

| Data | Script | Contains |
|---|---|---|
| PostgreSQL | `scripts/backup/backup-postgres.sh` | All application data — users, exams, questions, submissions, evaluations, results, audit logs, everything in the relational schema. |
| MinIO | `scripts/backup/backup-minio.sh` | Uploaded answer-script scans, generated PDF reports — everything in object storage. |

Redis is **not** backed up — it holds only the Celery broker/result backend
and rate-limit counters, all ephemeral/reconstructable state, not
source-of-truth data.

## Running a backup

```bash
scripts/backup/backup-postgres.sh   # writes backups/postgres/intelligrade_<db>_<timestamp>.sql.gz
scripts/backup/backup-minio.sh      # writes backups/minio/<timestamp>/
```

Both scripts:
- Read connection details from `.env.production` (must exist in the repo root).
- Verify the backup's integrity immediately after writing it (gzip
  integrity check for Postgres; non-empty file count for MinIO) and refuse
  to keep a corrupt/empty backup silently.
- Prune backups older than `BACKUP_RETENTION_DAYS` (default 14 — override
  via environment variable when invoking the script).

## Scheduling

Neither script self-schedules. Wire them into cron, a systemd timer, or
your orchestrator's scheduled-job primitive. A reasonable starting cadence:

```cron
# Daily Postgres dump at 02:00, MinIO mirror at 02:30
0 2 * * * /path/to/repo/scripts/backup/backup-postgres.sh >> /var/log/intelligrade-backup.log 2>&1
30 2 * * * /path/to/repo/scripts/backup/backup-minio.sh >> /var/log/intelligrade-backup.log 2>&1
```

## Off-host copies

`backups/` is a local directory on the host running Docker Compose — losing
that host loses the backups too unless they're additionally copied
off-host (S3/another region/offsite storage). This module does not
implement an off-host sync step; add one (e.g. `aws s3 sync backups/
s3://your-bucket/intelligrade-backups/` or `rclone`) before relying on
these backups for real disaster recovery — see `docs/disaster-recovery.md`.

## Restoring

See `docs/disaster-recovery.md` for the full recovery procedure. Quick
reference:

```bash
scripts/backup/restore-postgres.sh backups/postgres/intelligrade_intelligrade_<timestamp>.sql.gz
scripts/backup/restore-minio.sh backups/minio/<timestamp>
```

Both restore scripts prompt for confirmation (`restore-postgres.sh`
requires typing the database name; pass `--yes` to skip for scripted/DR
runs) since they overwrite live data.

## Verifying a backup is actually restorable

A backup that has never been test-restored is unverified. Periodically
(monthly is a reasonable cadence):

1. Spin up a throwaway Postgres/MinIO pair (not the production ones).
2. Restore the most recent backup into it.
3. Run `alembic current` and a handful of read queries / spot-check a
   restored file to confirm the data is actually usable, not just
   present.
4. Tear the throwaway environment down.
