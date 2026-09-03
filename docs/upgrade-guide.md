# Upgrade Guide (Module 08)

How to roll a new release out to a running production stack
(`docker-compose.prod.yml`) with zero (or minimal) downtime.

## Principles

- **Migrations must be backward-compatible with the previous release.**
  Since the old backend image keeps serving traffic until the new one is
  up, a migration that removes/renames a column the old code still reads
  will break the old instances mid-rollout. Additive migrations
  (new nullable column, new table) are always safe; destructive ones
  (drop column, rename, non-null-without-default) need an expand/contract
  approach across two releases.
- **Migrate before deploying**, never after — the new backend code may
  assume the new schema exists.
- **Backend before frontend** — the frontend's bundled `VITE_API_BASE_URL`
  points at the same reverse proxy regardless, but if a release adds a new
  API field the frontend depends on, the backend needs to be serving it
  before the new frontend build goes live.

## Procedure

1. **Confirm CI is green** for the release commit — `.github/workflows/`
   `test.yml`/`lint.yml`/`build.yml`/`security.yml` all passing, and
   `.github/workflows/deploy.yml` has pushed the new images to GHCR
   (tagged by commit SHA — see `docker/metadata-action` output).

2. **Take a fresh backup** before touching anything (see
   `docs/backup-guide.md`):
   ```bash
   scripts/backup/backup-postgres.sh
   ```

3. **Pull the new images**:
   ```bash
   docker compose -f docker-compose.prod.yml pull backend worker frontend
   ```

4. **Run migrations** against the live database, before restarting any
   application container:
   ```bash
   docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
   ```

5. **Roll the backend and worker**:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --no-deps backend worker
   ```
   Watch `/health/ready` return to `ready` before proceeding
   (`docker-compose.prod.yml`'s healthcheck already gates `depends_on`
   for anything that starts after, but confirm manually too):
   ```bash
   curl -k https://localhost/health/ready
   ```

6. **Roll the frontend**:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --no-deps frontend
   ```

7. **Smoke test**: `/health`, `/health/version` (confirm the version
   string matches the release), and a manual pass through the golden path
   in a browser (login → the feature area the release touched).

8. **Watch Grafana** (`docs/monitoring-guide.md`) for the 10–15 minutes
   after rollout — an elevated error rate or latency regression right
   after a deploy is the single most useful early-warning signal.

## If something goes wrong mid-rollout

Stop and follow `docs/rollback-guide.md` rather than trying to
forward-fix under pressure — a known-good previous image is one command
away as long as step 2's backup and the previous GHCR image tag both
still exist.

## Single-instance caveat

This module's `docker-compose.prod.yml` runs one instance of each service
— there is no blue/green or rolling-replica capability at this layer, so
"zero downtime" here means "a few seconds of container-restart downtime
during step 5/6," not a true zero-downtime rolling deploy. A genuinely
zero-downtime deploy requires a multi-instance orchestrator (Kubernetes,
ECS, etc.) with the images this module builds — see the "Planned cloud
path" section of `docs/deployment-guide.md`.
