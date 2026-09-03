"""ExtractedModelAnswer schemas — one OCR/AI-extracted model answer
awaiting/holding teacher verification (Module 06)."""

import uuid
from datetime import datetime

from app.schemas.base import BaseSchema


class ExtractedModelAnswerRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    document_id: uuid.UUID
    linked_answer_key_id: uuid.UUID | None = None
    question_number: str
    answer_text: str
    raw_ocr_text: str | None = None
    page_number: int | None = None
    display_order: int
    verification_status: str
    verified_by: uuid.UUID | None = None
    verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ExtractedModelAnswerUpdate(BaseSchema):
    """`raw_ocr_text`/`question_number`/`page_number`/`display_order`/
    `verification_status`/`verified_by`/`verified_at` are all system- or
    verification-action-managed — deliberately absent, never raw-PATCHed."""

    answer_text: str | None = None
    linked_answer_key_id: uuid.UUID | None = None
