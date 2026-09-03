"""
Async-safe MinIO/S3-compatible object storage client factory.

Mirrors `app.db.redis`'s singleton-factory shape exactly: `minio.Minio` is
itself synchronous (no async S3 SDK is a hard dependency here), so calls
through this client are wrapped in `asyncio.to_thread(...)` by
`app.services.storage_service` — this module only owns the client instance
and connectivity check, matching `redis.py`'s `get_redis_client()` /
`check_redis_connection()` split.
"""

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

_storage_client: Minio | None = None


def get_storage_client() -> Minio:
    """Return a process-wide singleton MinIO client."""
    global _storage_client
    if _storage_client is None:
        _storage_client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    return _storage_client


def check_storage_connection() -> bool:
    """Used by the readiness probe to verify object storage connectivity."""
    try:
        client = get_storage_client()
        client.bucket_exists(settings.MINIO_BUCKET_NAME)
        return True
    except S3Error as exc:
        logger.warning("storage_health_check_failed", error=str(exc))
        return False
    except Exception as exc:  # noqa: BLE001 - health checks must never raise
        logger.warning("storage_health_check_failed", error=str(exc))
        return False


def ensure_bucket_exists() -> None:
    """Create the configured bucket if it doesn't exist yet. Called once at startup."""
    client = get_storage_client()
    if not client.bucket_exists(settings.MINIO_BUCKET_NAME):
        client.make_bucket(settings.MINIO_BUCKET_NAME)
        logger.info("storage_bucket_created", bucket=settings.MINIO_BUCKET_NAME)
