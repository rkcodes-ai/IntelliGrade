# Monitoring Guide (Module 08)

## Stack

Prometheus + Grafana via `docker-compose.monitoring.yml`, run alongside
`docker-compose.prod.yml`:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml \
  --env-file .env.production up -d
```

- Prometheus (`monitoring/prometheus/prometheus.yml`) scrapes the
  backend's real `/metrics` endpoint every 15s, on the `internal` Docker
  network (never exposed publicly — nginx explicitly returns 404 for
  `/metrics` at the edge).
- Grafana auto-provisions the Prometheus datasource and the
  "IntelliGrade — API Overview" dashboard on container start — no manual
  click-through setup (`monitoring/grafana/provisioning/`).
- Grafana is published on `${GRAFANA_PORT:-3000}`; `GRAFANA_ADMIN_PASSWORD`
  must be set in `.env.production` (fails fast if unset).

## What `/metrics` actually exposes

Wired via `prometheus-fastapi-instrumentator` in `backend/app/main.py`.
Verified by booting the app and curling `/metrics` directly rather than
assumed from documentation — the real emitted metric names are:

- `http_requests_total` (counter; labels `handler`, `method`, `status` —
  status is bucketed as `2xx`/`4xx`/`5xx`, not the exact code)
- `http_request_duration_seconds_bucket` / `_count` / `_sum` (histogram;
  labels `handler`, `method`)
- `http_request_size_bytes_*` / `http_response_size_bytes_*`

There is no in-progress-request gauge by default — don't write an alert
rule expecting one.

## Dashboard panels (`monitoring/grafana/dashboards/intelligrade-overview.json`)

1. Request rate (req/s, by handler)
2. Error rate (5xx, req/s, by handler)
3. p95 latency by handler
4. p99 latency by handler
5. Total request volume (5m rate, stat)
6. Overall 5xx error ratio (stat)
7. Average response size (stat)

## Adding a new panel

1. Add a panel object to
   `monitoring/grafana/dashboards/intelligrade-overview.json` (validate
   with `python -c "import json; json.load(open('monitoring/grafana/dashboards/intelligrade-overview.json'))"`
   before committing — a syntax error here breaks Grafana's provisioning on
   next container start).
2. Restart Grafana (`docker compose -f docker-compose.prod.yml -f
   docker-compose.monitoring.yml restart grafana`) to pick up the change —
   provisioning runs on container start, not live-reload.
3. Prefer PromQL queries built from the verified metric names above; don't
   invent a metric name without confirming it against a live `/metrics`
   response first.

## Suggested alerting rules (not yet wired — no Alertmanager in this module)

This module ships Prometheus + Grafana for dashboards/trend visibility, not
alerting. If/when Alertmanager (or Grafana's own alerting) is added, these
are reasonable starting rules given the metrics above:

- `sum(rate(http_requests_total{status="5xx"}[5m])) / sum(rate(http_requests_total[5m])) > 0.05`
  for 5 minutes — elevated error rate.
- `histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m]))) > 1`
  for 10 minutes — p95 latency regression.
- Backend/worker container healthcheck failing 3 consecutive times (via
  your container orchestrator's own alerting, not Prometheus).

## Health probes vs. Prometheus — different jobs

`/health`, `/health/live`, `/health/ready` (see `docs/architecture.md`)
remain the target for container/orchestrator liveness+readiness checks —
fast, pass/fail, no historical data. Prometheus/Grafana are for trend
analysis and human-facing dashboards, not automated pass/fail gating.
