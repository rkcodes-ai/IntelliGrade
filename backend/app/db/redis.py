"""Async Redis client factory used for caching, rate limiting, and Celery broker checks."""

from redis import asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

_redis_client: Redis | None = None


def get_redis_client() -> Redis:
    """Return a process-wide singleton async Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URI,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
        )
    return _redis_client


async def check_redis_connection() -> bool:
    """Used by the readiness probe to verify Redis connectivity."""
    try:
        client = get_redis_client()
        return bool(await client.ping())
    except Exception as exc:
        logger.warning("redis_health_check_failed", error=str(exc))
        return False


async def close_redis_connection() -> None:
    """Gracefully close the Redis client on application shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
