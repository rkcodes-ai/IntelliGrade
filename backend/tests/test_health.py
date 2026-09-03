"""Smoke tests for the infrastructure health/liveness/version endpoints.

Readiness is intentionally not asserted "ready" here since it depends on
live Postgres/Redis connections (integration concern, not a unit smoke test).
`asyncio_mode = "auto"` (see pyproject.toml) means async tests need no marker.
"""

from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_liveness_returns_alive(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


async def test_readiness_reports_components(client: AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code in (200, 503)
    body = response.json()
    component_names = {c["name"] for c in body["components"]}
    assert component_names == {"database", "redis"}


async def test_version_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health/version")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "IntelliGrade"
    assert "version" in body
