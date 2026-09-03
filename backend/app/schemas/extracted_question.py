"""ExtractedQuestion schemas — one OCR/AI-extracted question awaiting/holding
teacher verification (Module 06)."""

import uuid
from datetime import datetime
from decimal import Decimal

from app.schemas.base import BaseSchema


class ExtractedQuestionRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    document_id: uuid.UUID
    linked_question_id: uuid.UUID | None = None
    question_number: str
    question_text: str
    raw_ocr_text: str | None = None
    detected_marks: Decimal | None = None
    final_marks: Decimal | None = None
    page_number: int | None = None
    display_order: int
    verification_status: str
    verified_by: uuid.UUID | None = None
    verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ExtractedQuestionUpdate(BaseSchema):
    """`raw_ocr_text`/`question_number`/`page_number`/`display_order`/
    `verification_status`/`verified_by`/`verified_at` are all system- or
    verification-action-managed — deliberately absent, never raw-PATCHed."""

    question_text: str | None = None
    final_marks: Decimal | None = None
    linked_question_id: uuid.UUID | None = None
