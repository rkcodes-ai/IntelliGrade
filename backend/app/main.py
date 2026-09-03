"""
Application factory and entrypoint.

Run locally with:
    uvicorn app.main:app --reload
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from prometheus_fastapi_instrumentator import Instrumentator

from app import models as _models  # noqa: F401 - registers all models on Base.metadata
from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.db.redis import close_redis_connection
from app.db.session import engine
from app.middleware.logging_middleware import AccessLogMiddleware
from app.middleware.rate_limit import DefaultRateLimitMiddleware, register_rate_limiting
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Startup/shutdown hooks: manage long-lived resources (DB engine, Redis)."""
    logger.info("application_startup", environment=settings.ENVIRONMENT)
    yield
    logger.info("application_shutdown")
    await engine.dispose()
    await close_redis_connection()


def create_application() -> FastAPI:
    """Application factory — builds and configures the FastAPI instance."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # --- Middleware (order matters: outermost registered last executes first) ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)

    register_rate_limiting(app)
    # Module 08 wired up `SlowAPIMiddleware` here to enforce `RATE_LIMIT_DEFAULT`
    # globally. Module 10's live deployment validation found it had gone
    # silently non-functional on this FastAPI version (route-introspection
    # incompatibility — see `app/middleware/rate_limit.py`'s module
    # docstring for the full root-cause). Replaced with
    # `DefaultRateLimitMiddleware`, which enforces the same limit without
    # depending on `SlowAPIMiddleware`'s broken route lookup.
    # `in_memory_fallback_enabled=True` on the `Limiter` (see
    # `app/middleware/rate_limit.py`) means a Redis outage degrades to an
    # in-process counter instead of failing open entirely.
    app.add_middleware(DefaultRateLimitMiddleware)
    register_exception_handlers(app)

    # --- Routers ---
    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    app.openapi = lambda: _custom_openapi(app)  # type: ignore[method-assign]

    # Module 08: real Prometheus metrics at `/metrics` (request count/
    # latency histograms/in-progress gauge, labeled by method+handler+
    # status). Not behind auth — same convention as `/health*` (a stable,
    # version-independent, credential-free path a scraper polls) — the
    # reverse proxy / network policy is what keeps it off the public
    # internet in a real deployment, see docs/monitoring-guide.md.
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    return app


def _custom_openapi(app: FastAPI) -> dict:
    """Customize generated OpenAPI schema (e.g. add security schemes later)."""
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["info"]["x-api-version"] = settings.API_V1_PREFIX
    app.openapi_schema = schema
    return app.openapi_schema


app = create_application()
