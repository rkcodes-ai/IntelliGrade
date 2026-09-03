# v1.0 Deployment Checklist

A release-gate checklist for shipping IntelliGrade v1.0 to a real
environment for the first time. This is deliberately narrower than
`docs/production-checklist.md` (the full pre-launch checklist covering
secrets, TLS, backups, monitoring, etc. — read that one too, in full,
before going live) — this document is the ordered sequence of steps
specific to a first v1.0 deployment.

## 1. Prove the infrastructure actually builds (the #1 unverified item)

This project was certified in a sandbox with no Docker daemon — every
Dockerfile/Compose file/nginx config was carefully constructed but never
built or run. **Before anything else:**

- [ ] `docker build --target production -t intelligrade-backend:1.0.0 ./backend`
- [ ] `docker build --target worker -t intelligrade-backend-worker:1.0.0 ./backend`
- [ ] `docker build --target production -f frontend/Dockerfile -t intelligrade-frontend:1.0.0 .` (run from repo root)
- [ ] `docker compose -f docker-compose.prod.yml config` (validates the compose file against your real Docker/Compose version)
- [ ] `nginx -t -c nginx/nginx.conf` (or equivalent config-test inside a throwaway nginx container) against the real `nginx/` config tree

If any of these fail, fix them **before** proceeding — everything below
assumes working images.

## 2. Provision real infrastructure

- [ ] Real PostgreSQL 16+ instance (managed or self-hosted)
- [ ] Real Redis 6+ instance, password-protected
- [ ] Real MinIO (or S3-compatible) bucket
- [ ] DNS pointed at the host that will run `nginx`
- [ ] A real, CA-issued TLS certificate for that domain (the self-signed
      one in `nginx/certs/` is sandbox/staging-only — see
      `nginx/certs/README.md`)

## 3. Secrets

- [ ] `.env.production` created from `.env.production.example`, every
      `REPLACE_ME_*` filled with a real, unique, generated value
- [ ] `.env.production` stored in a real secrets manager, not just the
      deploy host's filesystem
- [ ] `SECRET_KEY` generated via `openssl rand -hex 32` — confirmed not
      a placeholder (the app refuses to boot in production with one, but
      confirm before relying on that safety net)

## 4. Database

- [ ] `alembic upgrade head` run against the real database, before any
      application container starts
- [ ] Confirm all 13 migrations applied cleanly (`alembic current`
      should show the latest revision)
- [ ] RBAC/permission seed data confirmed present (query `permissions`/
      `roles` tables — should show 304 permissions, 4 system roles)

## 5. Deploy

- [ ] `docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build`
- [ ] All 7 services report healthy (`docker compose ps`)
- [ ] `curl https://<your-domain>/health/ready` returns `{"status":"ready",...}`
- [ ] `curl https://<your-domain>/metrics` returns 404 (confirms it's
      NOT exposed at the public edge)
- [ ] Bring up `docker-compose.monitoring.yml`; confirm Grafana's
      "IntelliGrade — API Overview" dashboard shows live data

## 6. Smoke test the golden path

- [ ] Log in as a seeded admin user
- [ ] Create an institution/academic hierarchy (or confirm seed data)
- [ ] Upload one answer script, confirm it OCRs successfully
- [ ] Run through Teacher Review → Result Finalization → Publish for one
      exam session
- [ ] Generate one report, confirm the PDF downloads and opens
- [ ] Confirm the published-result notification appears for the student

## 7. Backups

- [ ] `scripts/backup/backup-postgres.sh` run once, confirmed it produces
      a real, non-empty, integrity-verified archive
- [ ] `scripts/backup/backup-minio.sh` run once, same confirmation
- [ ] Both scripts scheduled (cron/systemd-timer) per `docs/backup-guide.md`
- [ ] A test restore performed at least once against a **non-production**
      target, per `docs/backup-guide.md`'s verification section

## 8. Go live

- [ ] Point DNS/load balancer at the new deployment
- [ ] Watch Grafana for the first 30-60 minutes for any error-rate/
      latency anomaly
- [ ] Confirm CI (`.github/workflows/`) is green on the deployed commit
      and `deploy.yml` has published images tagged with that commit's SHA

## Rollback readiness

Before declaring the deployment done, confirm you could roll back if
needed — see `docs/rollback-guide.md`. The previous state (in this case,
"no deployment") means rollback is simply stopping the stack; for the
*next* release, confirm the previous image tag is still pullable before
rolling forward.
