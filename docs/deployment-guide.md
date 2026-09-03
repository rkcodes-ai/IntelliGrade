# Deployment Guide

## Current state (Module 08)

A full production stack now exists: `docker-compose.prod.yml` (app stack),
`docker-compose.monitoring.yml` (Prometheus + Grafana overlay), an `nginx`
reverse proxy (`nginx/`) terminating TLS, and CI/CD
(`.github/workflows/security.yml`, `.github/workflows/deploy.yml`,
`.github/dependabot.yml`) building on top of the CI validation
(`docker.yml`) that already existed from Module 01. See
`docs/production-checklist.md` before a first real launch,
`docs/runbook.md` for day-to-day operations, `docs/upgrade-guide.md` /
`docs/rollback-guide.md` for release procedure, and
`docs/disaster-recovery.md` for full-loss recovery.

**Not validated by actually running Docker in this sandbox** — see
`KNOWN_LIMITATIONS.md`'s Module 08 section. Every file below was
constructed carefully against well-known patterns and cross-checked
manually, but the first time any of it is built/run for real should be
treated as the first real test, per `docs/production-checklist.md`.

## Container images

Both `backend/Dockerfile` and `frontend/Dockerfile` are multi-stage:

- **Backend**: `runtime-base` (python:3.13-slim + curl/libpq5/
  tesseract-ocr/libglib2.0-0) → `build-base` (adds build-essential/
  libpq-dev, compiler toolchain never copied into runtime images) → `deps`
  (pip install) → `production` (non-root `appuser`, `uvicorn --workers 4`,
  `HEALTHCHECK` against `/health`) / `worker` (non-root, runs
  `celery -A app.tasks.celery_app worker`, `HEALTHCHECK` via
  `celery inspect ping`) / `development` (hot reload, dev extras).
- **Frontend**: static assets built with `vite build` (with
  `VITE_API_BASE_URL`/`VITE_APP_NAME` baked in at build time via
  `ARG`/`ENV` — see `docker-compose.prod.yml`'s `build.args`), served by
  `nginxinc/nginx-unprivileged:1.27-alpine` (non-root by design, listens on
  8080) with SPA fallback routing, gzip, and long-cache headers on
  `/assets/` (see `frontend/nginx.conf`).

Build them directly:

```bash
docker build --target production -t intelligrade-backend:latest ./backend
docker build --target worker -t intelligrade-backend-worker:latest ./backend

# Frontend needs REPO-ROOT context (npm workspaces lockfile lives at the
# root, not inside frontend/) — run from the repository root:
docker build --target production -f frontend/Dockerfile \
  --build-arg VITE_API_BASE_URL=/api/v1 -t intelligrade-frontend:latest .
```

Or bring up the full stack via Compose — see `docs/runbook.md`.

## Target environments

| Environment | Purpose                          | Config source                       |
|--------------|-------------------------------------|--------------------------------------|
| `development`  | Local dev (Docker Compose or bare)     | `.env` (gitignored), `docker-compose.yml` |
| `staging`         | Pre-production validation                | `.env.production`-style file, same `docker-compose.prod.yml` |
| `production`         | Live system                                | `.env.production` (gitignored), `docker-compose.prod.yml` + `docker-compose.monitoring.yml`, `DEBUG=false`, docs disabled |

See [environment-guide.md](environment-guide.md) for the full variable list.

## Reverse proxy / TLS

`nginx/` (repo root) is the only service publishing host ports 80/443 in
`docker-compose.prod.yml` — it terminates TLS, proxies `/api/`+`/health`+
`/docs|redoc|openapi.json` to the backend and `/` to the frontend's static
container, and explicitly blocks `/metrics` at the public edge (Prometheus
reaches the backend directly on the internal Docker network instead). See
`nginx/certs/README.md` for replacing the sandbox's self-signed cert with a
real CA-issued one before production use.

## Planned cloud path (not yet implemented)

`infrastructure/terraform/` and `infrastructure/k8s/` remain reserved for a
future module: managed PostgreSQL/Redis, managed object storage, and real
container orchestration (Kubernetes or a managed platform) — this module's
`docker-compose.prod.yml` targets a single-host deployment, not a
multi-node cluster. See the "Single-instance caveat" in
`docs/upgrade-guide.md`.

## Release checklist

See `docs/upgrade-guide.md` for the full step-by-step procedure
(migrate-first, backend-then-frontend ordering, smoke test, Grafana
watch-window) and `docs/production-checklist.md` before a first launch.

## Secrets

Never bake secrets into images or commit them. Real values live only in
the gitignored `.env.production` — `.env.production.example` documents
every required variable with an obviously-unusable placeholder. See
[environment-guide.md](environment-guide.md) and
`docs/production-checklist.md`.
