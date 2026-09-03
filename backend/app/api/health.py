"""
Infrastructure probes: health, liveness, readiness, and version.

Deliberately unversioned (not under `/api/v1`) — load balancers, Kubernetes
probes, and uptime monitors expect these at a stable, version-independent
path.
"""

import asyncio

from fastapi import APIRouter, Request, Response, status

from app.core.config import get_settings
from app.db.redis import check_redis_connection
from app.db.session import check_database_connection
from app.middleware.rate_limit import limiter
from app.schemas.health import (
    ComponentStatus,
    HealthResponse,
    LivenessResponse,
    ReadinessResponse,
    VersionResponse,
)

router = APIRouter(prefix="/health", tags=["Health"])
settings = get_settings()


@router.get("", response_model=HealthResponse, summary="Overall service health")
@limiter.exempt  # type: ignore[untyped-decorator]  # slowapi ships no type stubs (ADR-005 precedent)
async def health(request: Request) -> HealthResponse:
    return HealthResponse(status="ok", environment=settings.ENVIRONMENT)


@router.get("/live", response_model=LivenessResponse, summary="Liveness probe")
@limiter.exempt  # type: ignore[untyped-decorator]
async def liveness(request: Request) -> LivenessResponse:
    """Process is up and able to serve traffic (no dependency checks)."""
    return LivenessResponse(status="alive")


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness probe")
@limiter.exempt  # type: ignore[untyped-decorator]
async def readiness(request: Request, response: Response) -> ReadinessResponse:
    """Process AND its critical dependencies (DB, Redis) are reachable."""
    db_healthy, redis_healthy = await asyncio.gather(
        check_database_connection(), check_redis_connection()
    )
    components = [
        ComponentStatus(name="database", healthy=db_healthy),
        ComponentStatus(name="redis", healthy=redis_healthy),
    ]
    is_ready = all(c.healthy for c in components)
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="ready" if is_ready else "not_ready", components=components)


@router.get("/version", response_model=VersionResponse, summary="Build/version info")
async def version() -> VersionResponse:
    return VersionResponse(
        name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
    )
