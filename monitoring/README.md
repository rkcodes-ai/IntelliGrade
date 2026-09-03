# Monitoring (Module 08)

Prometheus + Grafana, wired up via `docker-compose.monitoring.yml` (repo
root) as a separate overlay to the production app stack:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml \
  --env-file .env.production up -d
```

- `prometheus/prometheus.yml` — scrapes the backend's real `/metrics`
  endpoint (`prometheus-fastapi-instrumentator`, wired in
  `backend/app/main.py`) every 15s.
- `grafana/provisioning/` — auto-provisions the Prometheus datasource and
  the dashboard folder below on container start (no manual click-through).
- `grafana/dashboards/intelligrade-overview.json` — request rate, error
  rate, p95/p99 latency by handler, and response-size stats. Verified
  against the real metric names this backend actually exposes (not
  guessed) — see docs/monitoring-guide.md for how that was checked.

The backend's `/health`, `/health/live`, and `/health/ready` endpoints
(see [docs/architecture.md](../docs/architecture.md)) remain the
target for container/orchestrator liveness+readiness probes — Prometheus
is for trend/alerting, not pass/fail probes.

See [docs/monitoring-guide.md](../docs/monitoring-guide.md) for the full
guide (adding a panel, alerting rules, and this module's constraints).
