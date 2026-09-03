"""OCRJob schemas — one OCR execution attempt against an AnswerScript."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema

#: Mirrors `OCRJob.status`'s plain-string column (no DB CHECK constraint,
#: see `app/models/ocr_job.py`'s docstring).
OCRJobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class OCRJobRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    answer_script_id: uuid.UUID
    ocr_provider_id: uuid.UUID
    requested_ocr_provider_id: uuid.UUID | None = None
    fallback_reason: str | None = None
    celery_task_id: str | None = None
    status: OCRJobStatus
    priority: int
    retry_count: int
    max_retries: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class OCRJobCreate(BaseSchema):
    """
    Creates a new job row in `"queued"` status only -- does not itself
    enqueue a Celery task (see `OCRJob`'s docstring for why). `status`,
    `celery_task_id`, `retry_count`, and the timestamp fields are never
    client-supplied.
    """

    answer_script_id: uuid.UUID
    ocr_provider_id: uuid.UUID
    priority: int = Field(default=5, ge=1)
    max_retries: int = Field(default=3, ge=0)
