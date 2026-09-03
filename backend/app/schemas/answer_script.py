"""AnswerScript schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from app.schemas.base import BaseSchema

AnswerScriptStatus = Literal[
    "uploading",
    "uploaded",
    "validating",
    "validated",
    "failed_validation",
    "storing",
    "stored",
    "preprocessing",
    "ocr_queued",
    "ocr_running",
    "ocr_complete",
    "ocr_failed",
    "structuring",
    "completed",
    "failed",
    "cancelled",
]


class AnswerScriptRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    exam_session_id: uuid.UUID
    uploaded_by: uuid.UUID
    original_filename: str
    mime_type: str
    page_count: int | None = None
    file_size_bytes: int
    checksum_sha256: str | None = None
    storage_key: str | None = None
    status: AnswerScriptStatus
    failure_reason: str | None = None
    structured_content: dict[str, Any] | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AnswerScriptCreate(BaseSchema):
    """Used only to type the multipart form's non-file fields — the actual
    endpoint takes `exam_session_id` as a `Form(...)` field alongside an
    `UploadFile`, not a JSON body (see `app/api/v1/endpoints/answer_scripts.py`)."""

    exam_session_id: uuid.UUID


class AnswerScriptUpdate(BaseSchema):
    """Deliberately narrow — content fields (filename, checksum, storage_key,
    status, structured_content, ...) are pipeline-managed, never client-PATCHed.
    Only `is_active` is exposed for a manual admin override."""

    is_active: bool | None = None
