# Environment Guide

Four separate env templates exist — copy each to its real counterpart and
never commit the real files (all covered by root `.gitignore`).

| Template                     | Copy to                     | Consumed by                          |
|--------------------------------|--------------------------------|-----------------------------------------|
| `.env.example` (root)             | `.env`                            | `docker-compose.yml` (local dev)           |
| `.env.production.example` (root, Module 08) | `.env.production` | `docker-compose.prod.yml` + `docker-compose.monitoring.yml` |
| `backend/.env.example`               | `backend/.env`                       | FastAPI app (`app.core.config.Settings`)      |
| `frontend/.env.example`                 | `frontend/.env.local`                   | Vite (`import.meta.env`, validated by `src/config/env.ts`) |

## Root (`docker-compose.yml`) variables

General: `COMPOSE_PROJECT_NAME`, `ENVIRONMENT`.
Postgres: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`.
Redis: `REDIS_PORT`, `REDIS_PASSWORD`.
MinIO: `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_API_PORT`, `MINIO_CONSOLE_PORT`, `MINIO_BUCKET_NAME`.
Backend: `BACKEND_PORT`, `SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`.
Frontend: `FRONTEND_PORT`, `VITE_API_BASE_URL`.

## Backend variables

See `backend/.env.example` for the full, current list with defaults. Grouped by concern:

- **General**: `ENVIRONMENT`, `DEBUG`, `HOST`, `PORT`
- **Security**: `SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`
- **CORS**: `CORS_ORIGINS` (comma-separated)
- **Database**: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `DATABASE_ECHO`, `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_POOL_RECYCLE_SECONDS` (Module 08 — avoids stale-connection errors behind a managed DB/load balancer), `DATABASE_CONNECT_TIMEOUT_SECONDS` (Module 08 — bounds `/health/ready`'s DB check latency when the DB is down), `SLOW_QUERY_THRESHOLD_MS` (Module 08 — logs any query slower than this; `0` disables)
- **Redis**: `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DB`, `REDIS_CONNECT_TIMEOUT_SECONDS` (Module 08 — same rationale as the database connect timeout)
- **Object storage**: `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET_NAME`, `MINIO_SECURE`
- **Rate limiting**: `RATE_LIMIT_DEFAULT`
- **Logging**: `LOG_LEVEL`, `LOG_JSON`

All variables are typed and validated at startup by
`app.core.config.Settings` (Pydantic Settings) — an invalid value fails
fast at process start rather than surfacing as a runtime bug later.

## Frontend variables

Only variables prefixed `VITE_` are exposed to client code (Vite
convention — anything else is silently unavailable in the browser bundle,
by design, to avoid leaking server secrets into client JS).

- `VITE_API_BASE_URL` — backend API base URL (validated as a URL by `src/config/env.ts`)
- `VITE_APP_NAME` — display name, defaults to `IntelliGrade`

## Secret generation

```bash
# SECRET_KEY
openssl rand -hex 32
```

Never reuse the `change_me_dev_only` / `dev-only-insecure-secret-change-me`
defaults outside local development — staging and production must set real
values via the deployment platform's secret manager (see
[deployment-guide.md](deployment-guide.md#secrets)).

## Production environment (Module 08)

`.env.production.example` (root) is the production counterpart to
`backend/.env.example` — it's consumed by `docker-compose.prod.yml` both
directly (Postgres/Redis/MinIO/nginx variables) and via
`env_file: .env.production` for the backend/worker services. Copy it to
`.env.production`, replace every `REPLACE_ME_*` placeholder with a real,
unique value, and never commit the result — see
`docs/production-checklist.md` for the full pre-launch list. Unlike the
dev compose, Redis requires `REDIS_PASSWORD` to be set (enforced via
`redis-server --requirepass`), and `GRAFANA_ADMIN_PASSWORD` is required by
`docker-compose.monitoring.yml` (fails fast if unset).
