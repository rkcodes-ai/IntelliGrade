# Docker

Application Dockerfiles live next to their source (`backend/Dockerfile`,
`frontend/Dockerfile`) — the standard convention, so `docker build` context
matches the app directory. This directory holds **infrastructure-only**
configuration for the services in `docker-compose.yml` that don't have an
application of their own:

- `postgres/` — reserved for custom init scripts (none needed yet; the
  `pgcrypto` extension is enabled via the baseline Alembic migration instead)
- `redis/` — reserved for a custom `redis.conf` if defaults stop being enough
- `minio/` — reserved for bucket-policy bootstrap scripts
- `backend/`, `frontend/` — reserved for future prod-only compose overrides

Empty in Module 01 by design.
