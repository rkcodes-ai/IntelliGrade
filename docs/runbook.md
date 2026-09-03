# Operations Runbook (Module 08)

Day-to-day operational commands for the production stack
(`docker-compose.prod.yml` + optional `docker-compose.monitoring.yml`
overlay). See `docs/production-checklist.md` before first launch and
`docs/incident-response-guide.md` when something is actually on fire.

## Starting / stopping the stack

```bash
# Bring the full app stack up (builds images if not already built)
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build

# Add monitoring (Prometheus + Grafana)
docker compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml \
  --env-file .env.production up -d

# Stop everything (containers only, volumes preserved)
docker compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml down

# Stop AND destroy volumes (DESTRUCTIVE — deletes Postgres/Redis/MinIO/Grafana data)
docker compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml down -v
```

## Checking service health

```bash
docker compose -f docker-compose.prod.yml ps                    # container status + healthcheck state
curl -k https://localhost/health                                 # overall
curl -k https://localhost/health/live                             # liveness
curl -k https://localhost/health/ready                             # readiness (DB + Redis)
docker compose -f docker-compose.prod.yml logs -f backend          # tail backend logs
docker compose -f docker-compose.prod.yml logs -f worker            # tail Celery worker logs
docker compose -f docker-compose.prod.yml exec worker \
  celery -A app.tasks.celery_app inspect active                     # in-flight Celery tasks
```

## Common tasks

### Rolling out a new backend/worker/frontend image

See `docs/upgrade-guide.md` for the full procedure (migration-first,
backend-then-frontend ordering). Quick version:

```bash
docker compose -f docker-compose.prod.yml pull backend worker frontend
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
docker compose -f docker-compose.prod.yml up -d --no-deps backend worker frontend
```

### Restarting a single service

```bash
docker compose -f docker-compose.prod.yml restart backend
```

### Scaling the worker

```bash
docker compose -f docker-compose.prod.yml up -d --no-deps --scale worker=3 worker
```

### Running a one-off backend shell (e.g. for a manual Alembic/data fix)

```bash
docker compose -f docker-compose.prod.yml exec backend bash
```

### Backups

```bash
scripts/backup/backup-postgres.sh    # see docs/backup-guide.md
scripts/backup/backup-minio.sh
```

### Regenerating the self-signed TLS cert (staging/local only)

```bash
scripts/generate-self-signed-cert.sh
docker compose -f docker-compose.prod.yml restart nginx
```

## Where to look when something's wrong

| Symptom | Look at |
|---|---|
| 502/504 from nginx | `docker compose logs nginx`, then `docker compose logs backend` — nginx can't reach backend, or backend is slow/down. |
| `/health/ready` returns `not_ready` | `docker compose logs backend` for `database_health_check_failed` / `redis_health_check_failed`; check `postgres`/`redis` container health directly. |
| Slow API responses | Grafana "p95/p99 latency by handler" panel (`docs/monitoring-guide.md`); backend logs for `slow_query` events. |
| Elevated 5xx rate | Grafana "Error rate" panel; `docker compose logs backend`. |
| Elevated 429s | Expected under real load spikes — global rate limiting (`SlowAPIMiddleware`) is working as designed; check `RATE_LIMIT_DEFAULT` is sized correctly for real traffic, not a bug per se. |
| Celery tasks not running | `docker compose logs worker`; `celery -A app.tasks.celery_app inspect active`/`inspect registered` inside the worker container — confirm the expected task names are registered (`app.tasks.celery_app`'s `include` list). |
| Disk filling up | `nginx_cache`, `postgres_data`, and `backups/` are the usual growth points — check volume sizes with `docker system df -v`. |

See `docs/incident-response-guide.md` for escalation and post-incident
process, and `docs/disaster-recovery.md` for full data-loss scenarios.
