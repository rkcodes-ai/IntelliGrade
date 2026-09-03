"""UploadJob schemas."""

import uuid
from datetime import datetime
from typing import Literal

from app.schemas.base import BaseSchema

UploadJobStatus = Literal["pending", "in_progress", "completed", "failed", "cancelled"]


class UploadJobRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    answer_script_id: uuid.UUID
    upload_session_token: str
    total_chunks: int | None = None
    chunks_received: int
    bytes_received: int
    total_bytes: int | None = None
    status: UploadJobStatus
    retry_count: int
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class UploadJobInitRequest(BaseSchema):
    """Body of `POST /answer-scripts/upload-init` (JSON, before any bytes flow)."""

    exam_session_id: uuid.UUID
    original_filename: str
    mime_type: str
    total_bytes: int
    total_chunks: int
