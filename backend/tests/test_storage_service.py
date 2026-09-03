"""StorageService unit tests against a fake in-memory Minio-like client (no real MinIO server)."""

from collections.abc import Iterator
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from minio.error import S3Error

from app.core.exceptions import NotFoundError
from app.services.storage_service import (
    StorageService,
    build_archive_key,
    build_original_key,
    build_page_key,
    build_temp_chunk_key,
    compute_sha256,
)


@pytest.fixture(autouse=True)
def _fake_storage() -> Iterator[None]:
    """Overrides `conftest.py`'s autouse fixture of the same name (module-level
    fixtures shadow conftest fixtures) — this file exercises the REAL
    `StorageService` implementation against a mocked `Minio` client, not the
    in-memory dict stand-in every other test file uses."""
    yield


def _s3_error(code: str) -> S3Error:
    return S3Error(
        code=code,
        message="test",
        resource="test",
        request_id="test",
        host_id="test",
        response=MagicMock(),
    )


def test_compute_sha256_is_deterministic() -> None:
    assert compute_sha256(b"hello") == compute_sha256(b"hello")
    assert compute_sha256(b"hello") != compute_sha256(b"world")


def test_build_key_helpers() -> None:
    import uuid

    inst = uuid.uuid4()
    script = uuid.uuid4()
    assert build_original_key(inst, script, "a.pdf") == f"{inst}/{script}/original/a.pdf"
    assert build_page_key(inst, script, 3, ".png") == f"{inst}/{script}/pages/0003.png"
    session = uuid.uuid4()
    assert build_temp_chunk_key(session, 5) == f"tmp/{session}/chunks/000005"
    assert build_archive_key("a/b/c") == "archive/a/b/c"


def test_put_bytes_sync_writes_and_returns_meta() -> None:
    client = MagicMock()
    service = StorageService(client=client)

    meta = service.put_bytes_sync("key1", b"hello world", "text/plain")

    client.put_object.assert_called_once()
    assert meta.key == "key1"
    assert meta.size_bytes == len(b"hello world")
    assert meta.checksum_sha256 == compute_sha256(b"hello world")
    assert meta.content_type == "text/plain"


def test_get_bytes_sync_reads_and_releases() -> None:
    client = MagicMock()
    response = MagicMock()
    response.read.return_value = b"payload"
    client.get_object.return_value = response

    service = StorageService(client=client)
    result = service.get_bytes_sync("key1")

    assert result == b"payload"
    response.close.assert_called_once()
    response.release_conn.assert_called_once()


def test_get_bytes_sync_raises_not_found_for_missing_key() -> None:
    client = MagicMock()
    client.get_object.side_effect = _s3_error("NoSuchKey")
    service = StorageService(client=client)

    with pytest.raises(NotFoundError):
        service.get_bytes_sync("missing-key")


def test_get_bytes_sync_reraises_other_s3_errors() -> None:
    client = MagicMock()
    client.get_object.side_effect = _s3_error("InternalError")
    service = StorageService(client=client)

    with pytest.raises(S3Error):
        service.get_bytes_sync("key1")


def test_object_exists_sync_true_when_stat_succeeds() -> None:
    client = MagicMock()
    service = StorageService(client=client)
    assert service.object_exists_sync("key1") is True


@pytest.mark.parametrize("code", ["NoSuchKey", "NoSuchObject"])
def test_object_exists_sync_false_for_missing_object(code: str) -> None:
    client = MagicMock()
    client.stat_object.side_effect = _s3_error(code)
    service = StorageService(client=client)
    assert service.object_exists_sync("key1") is False


def test_object_exists_sync_reraises_other_errors() -> None:
    client = MagicMock()
    client.stat_object.side_effect = _s3_error("InternalError")
    service = StorageService(client=client)
    with pytest.raises(S3Error):
        service.object_exists_sync("key1")


def test_delete_sync_calls_remove_object() -> None:
    client = MagicMock()
    service = StorageService(client=client)
    service.delete_sync("key1")
    client.remove_object.assert_called_once_with(service._bucket, "key1")


def test_copy_sync_calls_copy_object() -> None:
    client = MagicMock()
    service = StorageService(client=client)
    service.copy_sync("src", "dst")
    client.copy_object.assert_called_once()


def test_presigned_get_url_sync_returns_url() -> None:
    client = MagicMock()
    client.presigned_get_object.return_value = "http://example.test/key1"
    service = StorageService(client=client)

    url = service.presigned_get_url_sync("key1", expires_seconds=120)

    assert url == "http://example.test/key1"
    args, kwargs = client.presigned_get_object.call_args
    assert kwargs["expires"] == timedelta(seconds=120)


def test_archive_sync_copies_then_deletes_original() -> None:
    client = MagicMock()
    service = StorageService(client=client)

    archive_key = service.archive_sync("a/b/original/file.pdf")

    assert archive_key == "archive/a/b/original/file.pdf"
    client.copy_object.assert_called_once()
    client.remove_object.assert_called_once_with(service._bucket, "a/b/original/file.pdf")


def test_promote_temp_to_permanent_sync() -> None:
    client = MagicMock()
    stat = MagicMock(size=42, etag='"abc123"', content_type="image/png")
    client.stat_object.return_value = stat
    service = StorageService(client=client)

    meta = service.promote_temp_to_permanent_sync("tmp/key", "perm/key")

    assert meta.key == "perm/key"
    assert meta.size_bytes == 42
    assert meta.checksum_sha256 == "abc123"
    assert meta.content_type == "image/png"
    client.remove_object.assert_called_once_with(service._bucket, "tmp/key")


async def test_async_wrappers_delegate_to_sync_methods() -> None:
    client = MagicMock()
    client.presigned_get_object.return_value = "http://example.test/key1"
    response = MagicMock()
    response.read.return_value = b"payload"
    client.get_object.return_value = response
    stat = MagicMock(size=1, etag='"x"', content_type="text/plain")
    client.stat_object.return_value = stat

    service = StorageService(client=client)

    meta = await service.put_bytes("key1", b"data", "text/plain")
    assert meta.key == "key1"

    data = await service.get_bytes("key1")
    assert data == b"payload"

    exists = await service.object_exists("key1")
    assert exists is True

    await service.delete("key1")
    client.remove_object.assert_called_with(service._bucket, "key1")

    url = await service.presigned_get_url("key1")
    assert url == "http://example.test/key1"

    promoted = await service.promote_temp_to_permanent("tmp/key", "perm/key")
    assert promoted.key == "perm/key"
