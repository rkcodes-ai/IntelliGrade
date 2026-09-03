"""OfficialExamDocument schemas."""

import uuid
from datetime import datetime
from typing import Literal

from app.schemas.base import BaseSchema

OfficialExamDocumentType = Literal["question_paper", "model_answer", "mark_scheme"]

OfficialExamDocumentOCRStatus = Literal[
    "uploading",
    "uploaded",
    "storing",
    "stored",
    "preprocessing",
    "ocr_running",
    "ocr_complete",
    "completed",
    "failed",
    "cancelled",
]

OfficialExamDocumentVerificationStatus = Literal["not_started", "in_progress", "verified"]


class OfficialExamDocumentRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    exam_id: uuid.UUID
    uploaded_by: uuid.UUID
    document_type: OfficialExamDocumentType
    original_filename: str
    mime_type: str
    file_size_bytes: int
    checksum_sha256: str | None = None
    storage_key: str | None = None
    page_count: int | None = None
    raw_ocr_text: str | None = None
    ocr_status: OfficialExamDocumentOCRStatus
    verification_status: OfficialExamDocumentVerificationStatus
    failure_reason: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class OfficialExamDocumentCreate(BaseSchema):
    """Types the multipart form's non-file fields — the actual endpoint
    takes `exam_id`/`document_type` as `Form(...)` fields alongside an
    `UploadFile`, not a JSON body, mirroring `AnswerScriptCreate`."""

    exam_id: uuid.UUID
    document_type: OfficialExamDocumentType


class OfficialExamDocumentUpdate(BaseSchema):
    """Deliberately narrow — content fields are pipeline-managed, never
    client-PATCHed. Only `is_active` is exposed for a manual admin override."""

    is_active: bool | None = None
