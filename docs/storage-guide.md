# Object Storage Guide (Module 05)

`app/services/storage_service.py`'s `StorageService` is the first real code
in this repository to talk to MinIO — the service has been provisioned in
`docker-compose.yml` since Module 01 but was config-only (no client, no
read/write path) until this module. See ADR-026 in
[ARCHITECTURE_DECISIONS.md](../ARCHITECTURE_DECISIONS.md).

## Why MinIO, and why a thin wrapper

MinIO is S3-API-compatible, so `StorageService` is written entirely
against the `minio` Python SDK's method surface (`put_object`,
`get_object`, `stat_object`, `remove_object`, `copy_object`,
`presigned_get_object`) — a future migration to real AWS S3 would mean
swapping the client construction (`app/db/storage.py::get_storage_client`)
and endpoint config, not rewriting every caller. Every other service in
the codebase depends on `StorageService`'s method surface, never on the
`minio` SDK directly.

## Client lifecycle

`app/db/storage.py` exposes a lazily-constructed, process-wide singleton
`Minio` client (`get_storage_client()`), configured from
`MINIO_ENDPOINT`/`MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY`/`MINIO_SECURE` (see
`backend/.env.example`). `StorageService.__init__` accepts an optional
`client` override for testing — the app never constructs more than one
real client per process.

## Sync core + async wrappers

`minio.Minio` is a **synchronous** client. Celery tasks run outside an
event loop and call the `_sync` methods directly
(`put_bytes_sync`/`get_bytes_sync`/`object_exists_sync`/`delete_sync`/
`copy_sync`/`presigned_get_url_sync`/`archive_sync`/
`promote_temp_to_permanent_sync`). FastAPI endpoints run inside an event
loop, so they call the async wrappers (`put_bytes`/`get_bytes`/`object_exists`/
`delete`/`presigned_get_url`/`promote_temp_to_permanent`), each a thin
`asyncio.to_thread(...)` delegation to its sync counterpart — the simplest
way to call a blocking SDK from async code without introducing a second
storage client implementation.

## Key layout

All objects live under one configured bucket (`MINIO_BUCKET_NAME`), keyed
by a fixed scheme so no separate key-index table is needed — the key
itself encodes ownership and purpose:

```text
{institution_id}/{answer_script_id}/original/{filename}
{institution_id}/{answer_script_id}/pages/{page_number:04d}.{ext}
tmp/{upload_session_id}/chunks/{chunk_index:06d}
archive/{institution_id}/{answer_script_id}/original/{filename}
```

Built by the four `build_*_key()` helper functions
(`build_original_key`/`build_page_key`/`build_temp_chunk_key`/
`build_archive_key`) — callers never hand-format a key string, so the
scheme can change in one place if it ever needs to.

- **Original**: the exact bytes uploaded by the client, stored once,
  never modified in place.
- **Pages**: one PNG per physical page, written during Stage 4 (Image
  Processing) — the *preprocessed* image, not the raw page extracted from
  the original PDF/image.
- **Temp chunks**: reserved for a future chunked/resumable upload
  implementation (see [Chunked upload readiness](#chunked-upload-readiness)
  below) — not yet written by any code path.
- **Archive**: a cold-storage prefix, populated only by
  `archive_sync()`/`archive()` (see below).

## Metadata and checksums

Every write returns a `StorageObjectMeta` (`key`, `size_bytes`,
`checksum_sha256`, `content_type`) — never the raw MinIO SDK response
object, so callers never depend on `minio` SDK types outside this module.
`compute_sha256()` is computed **before** the write and returned alongside
it (not re-derived from the SDK's `etag`, which for a single-part PUT
happens to equal the MD5, not SHA-256, of the object). The one exception is
`promote_temp_to_permanent_sync()`, whose returned `checksum_sha256` comes
from `stat_object().etag` (stripped of surrounding quotes) — acceptable
there since it's describing an object this service already wrote and
checksummed once at upload time; the promoted copy is a same-bytes
`copy_object`, not a re-upload.

## Temporary vs. permanent storage

`promote_temp_to_permanent(_sync)` copies an object from its temp key to
its permanent key, then deletes the temp copy — used for the (currently
unwritten) chunked-upload-assembly path where chunks would be
concatenated into a `tmp/` object before promotion to
`{institution_id}/{answer_script_id}/original/{filename}`. Today,
`AnswerScriptService.upload()` writes directly to the permanent key in one
`put_bytes` call (small/single-request uploads only) — see
[Chunked upload readiness](#chunked-upload-readiness).

## Archival (placeholder)

`archive_sync()`/`archive()` copy an object under an `archive/` prefix and
delete the original — a **placeholder** cold-storage move, not a real
lifecycle policy. A production implementation would instead configure a
MinIO/S3 lifecycle rule (transition to a colder storage class after N
days) rather than an application-level copy+delete, deferred until an
actual data-retention policy exists for this project.

## Virus-scan placeholder

`AnswerScriptService.scan_candidate()` calls
`scan_for_viruses_placeholder()` (`app/services/answer_script_service.py`)
on every uploaded file's bytes, immediately after format/size validation
and before the checksum/duplicate check. It is a deliberate no-op — no
scanning engine is wired in — but a real, named, always-invoked extension
point: a future integration (e.g. ClamAV) replaces that one function's
body without touching `validate_candidate`, `upload()`, or any caller.
Treat any file accepted by `POST /answer-scripts` today as **not**
actually virus-scanned.

## Chunked upload readiness

`build_temp_chunk_key()` and `promote_temp_to_permanent(_sync)` exist so a
future chunked/resumable upload flow (large files, flaky connections) can
be added without a storage-layer redesign: a client would `PUT` numbered
chunks to `tmp/{session}/chunks/{index}`, a finalize endpoint would
concatenate them and call `promote_temp_to_permanent`. **No endpoint
implements this today** — `POST /answer-scripts` is a single
multipart-form-data request, sized by `UPLOAD_MAX_FILE_SIZE_BYTES`. See
[KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md).

## Testing

`tests/test_storage_service.py` (16 tests) exercises the **real**
`StorageService` implementation against a `MagicMock` Minio client — this
required a module-level `_fake_storage` autouse fixture that shadows
`conftest.py`'s global autouse fixture (which otherwise monkeypatches
`StorageService`'s methods for every other test in the suite, so no test
accidentally makes a real network call). Every other test file in the
backend suite runs against that global in-memory-dict fake instead (see
`conftest.py`'s `_FAKE_BUCKET`), since almost every test only needs
"storage round-trips bytes," not real MinIO wire behavior.

## Related documents

- [ocr-pipeline-guide.md](ocr-pipeline-guide.md) — how the OCR pipeline
  calls `StorageService` during Stages 3/4.
- [database-standards.md](database-standards.md) — `AnswerScript`/
  `AnswerScriptPage`'s `storage_key`/`checksum_sha256` columns.
