"""OCRResult schemas — persisted OCR output for one AnswerScriptPage (Module 05)."""

import uuid
from datetime import datetime
from decimal import Decimal

from app.schemas.base import BaseSchema


class OCRResultRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    answer_script_page_id: uuid.UUID
    ocr_job_id: uuid.UUID
    raw_text: str
    normalized_text: str | None = None
    average_confidence: Decimal
    language: str
    rotation_degrees: Decimal
    reading_order_verified: bool
    provider_version: str | None = None
    processing_time_ms: int | None = None
    image_resolution: str | None = None
    raw_response_reference: str | None = None
    created_at: datetime
    updated_at: datetime
