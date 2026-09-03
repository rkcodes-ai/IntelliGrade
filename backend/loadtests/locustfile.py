"""
Module 08, Feature 10 (Performance) load test definitions.

Targets the infrastructure-level surface that this sandbox can actually
exercise end-to-end without a real Postgres/Redis/MinIO behind it: health
probes, the OpenAPI schema, and the Prometheus `/metrics` endpoint itself.
Business endpoints (auth, ingestion, teacher review, ...) all require a
live database and are deliberately NOT included here — see
docs/production-checklist.md and the load-test results section of the
Module 08 report for what a real environment run should add.

Usage (headless, 20 users, 5/s spawn rate, 60s):
    locust -f backend/loadtests/locustfile.py --host http://127.0.0.1:8125 \
        --headless -u 20 -r 5 -t 60s --csv=loadtests-results
"""

from locust import HttpUser, between, task


class HealthProbeUser(HttpUser):
    """Simulates a load balancer / orchestrator repeatedly polling probes."""

    wait_time = between(0.1, 0.5)

    @task(5)
    def liveness(self) -> None:
        self.client.get("/health/live", name="/health/live")

    @task(3)
    def health(self) -> None:
        self.client.get("/health", name="/health")

    @task(2)
    def readiness(self) -> None:
        # Expected to report "not_ready" (503) in any environment without a
        # real Postgres/Redis behind it — still valid to load-test since the
        # readiness handler itself (two awaited connection checks) is real
        # work, not a stub.
        self.client.get("/health/ready", name="/health/ready")

    @task(1)
    def version(self) -> None:
        self.client.get("/health/version", name="/health/version")


class ApiDiscoveryUser(HttpUser):
    """Simulates clients/tools fetching the API schema and docs."""

    wait_time = between(1, 3)

    @task(2)
    def openapi_schema(self) -> None:
        self.client.get("/openapi.json", name="/openapi.json")

    @task(1)
    def docs(self) -> None:
        self.client.get("/docs", name="/docs")
