"""
Object storage service for the Answer Script upload/OCR pipeline (Module 05).

`minio.Minio` is a synchronous client, so this module exposes a `_sync`
core (used directly by Celery tasks, which run outside an event loop) plus
thin `asyncio.to_thread(...)` wrappers (used by FastAPI endpoints). This is
the first real code in the repo to talk to the MinIO service that has been
provisioned in `docker-compose.yml` since Module 01 but never used — see
ADR-026.

Key layout (all objects live under the single configured bucket):
    {institution_id}/{answer_script_id}/original/{filename}
    {institution_id}/{answer_script_id}/pages/{page_number:04d}.{ext}
    tmp/{upload_session_id}/chunks/{chunk_index:06d}
    archive/{institution_id}/{answer_script_id}/original/{filename}
"""

import asyncio
import hashlib
import io
import uuid
from dataclasses import dataclass
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.storage import get_storage_client

settings = get_settings()
logger = get_logger(__name__)


@dataclass(frozen=True)
class StorageObjectMeta:
    """What callers need after a successful write — never the raw MinIO SDK object."""

    key: str
    size_bytes: int
    checksum_sha256: str
    content_type: str


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_original_key(
    institution_id: uuid.UUID, answer_script_id: uuid.UUID, filename: str
) -> str:
    return f"{institution_id}/{answer_script_id}/original/{filename}"


def build_page_key(
    institution_id: uuid.UUID, answer_script_id: uuid.UUID, page_number: int, extension: str
) -> str:
    return f"{institution_id}/{answer_script_id}/pages/{page_number:04d}.{extension.lstrip('.')}"


def build_region_crop_key(
    institution_id: uuid.UUID, answer_script_id: uuid.UUID, page_number: int, region_index: int
) -> str:
    """Document Intelligence milestone — one crop per detected
    DIAGRAM/TABLE/EQUATION region, kept alongside its page's own key
    namespace so a region's origin is obvious from its storage key alone."""
    return (
        f"{institution_id}/{answer_script_id}/pages/{page_number:04d}"
        f"/regions/{region_index:04d}.png"
    )


def build_temp_chunk_key(upload_session_id: uuid.UUID, chunk_index: int) -> str:
    return f"tmp/{upload_session_id}/chunks/{chunk_index:06d}"


def build_archive_key(original_key: str) -> str:
    return f"archive/{original_key}"


class StorageService:
    """Thin, swappable wrapper over the configured object-storage backend.

    Only MinIO/S3 is implemented (`Minio` client) — a future non-MinIO
    backend would be a new class satisfying the same method surface, not a
    rewrite of every caller (see ADR-026).
    """

    def __init__(self, client: Minio | None = None) -> None:
        self._client = client or get_storage_client()
        self._bucket = settings.MINIO_BUCKET_NAME

    # ---- sync core (Celery tasks call these directly) ----

    def put_bytes_sync(self, key: str, data: bytes, content_type: str) -> StorageObjectMeta:
        checksum = compute_sha256(data)
        self._client.put_object(
            self._bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        logger.info("storage_object_written", key=key, size_bytes=len(data))
        return StorageObjectMeta(
            key=key, size_bytes=len(data), checksum_sha256=checksum, content_type=content_type
        )

    def get_bytes_sync(self, key: str) -> bytes:
        try:
            response = self._client.get_object(self._bucket, key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                raise NotFoundError(f"Storage object not found: {key}") from exc
            raise

    def object_exists_sync(self, key: str) -> bool:
        try:
            self._client.stat_object(self._bucket, key)
            return True
        except S3Error as exc:
            if exc.code in ("NoSuchKey", "NoSuchObject"):
                return False
            raise

    def delete_sync(self, key: str) -> None:
        self._client.remove_object(self._bucket, key)
        logger.info("storage_object_deleted", key=key)

    def copy_sync(self, source_key: str, dest_key: str) -> None:
        from minio.commonconfig import CopySource

        self._client.copy_object(self._bucket, dest_key, CopySource(self._bucket, source_key))
        logger.info("storage_object_copied", source_key=source_key, dest_key=dest_key)

    def presigned_get_url_sync(self, key: str, expires_seconds: int = 3600) -> str:
        url: str = self._client.presigned_get_object(
            self._bucket, key, expires=timedelta(seconds=expires_seconds)
        )
        return url

    def archive_sync(self, key: str) -> str:
        """Placeholder cold-storage move: copies the object under an
        `archive/` prefix and removes the original. A real implementation
        would instead set a lifecycle policy or move to a colder storage
        class — deferred until an actual retention policy exists (see
        `docs/storage-guide.md`)."""
        archive_key = build_archive_key(key)
        self.copy_sync(key, archive_key)
        self.delete_sync(key)
        logger.info("storage_object_archived", key=key, archive_key=archive_key)
        return archive_key

    def promote_temp_to_permanent_sync(
        self, temp_key: str, permanent_key: str
    ) -> StorageObjectMeta:
        """Copies a temp-storage object to its permanent key, deletes the
        temp object, and returns fresh metadata for the permanent copy."""
        self.copy_sync(temp_key, permanent_key)
        stat = self._client.stat_object(self._bucket, permanent_key)
        self.delete_sync(temp_key)
        return StorageObjectMeta(
            key=permanent_key,
            size_bytes=stat.size or 0,
            checksum_sha256=(stat.etag or "").strip('"'),
            content_type=stat.content_type or "application/octet-stream",
        )

    # ---- async wrappers (FastAPI endpoints call these) ----

    async def put_bytes(self, key: str, data: bytes, content_type: str) -> StorageObjectMeta:
        return await asyncio.to_thread(self.put_bytes_sync, key, data, content_type)

    async def get_bytes(self, key: str) -> bytes:
        return await asyncio.to_thread(self.get_bytes_sync, key)

    async def object_exists(self, key: str) -> bool:
        return await asyncio.to_thread(self.object_exists_sync, key)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.delete_sync, key)

    async def presigned_get_url(self, key: str, expires_seconds: int = 3600) -> str:
        return await asyncio.to_thread(self.presigned_get_url_sync, key, expires_seconds)

    async def promote_temp_to_permanent(
        self, temp_key: str, permanent_key: str
    ) -> StorageObjectMeta:
        return await asyncio.to_thread(self.promote_temp_to_permanent_sync, temp_key, permanent_key)
