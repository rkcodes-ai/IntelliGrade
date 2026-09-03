"""OCRLine schemas — one text line within an OCRBlock (Module 05)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema
from app.schemas.ocr_word import OCRWordRead


class OCRLineRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    ocr_block_id: uuid.UUID
    text: str
    reading_order: int
    bbox_left: int
    bbox_top: int
    bbox_width: int
    bbox_height: int
    confidence: Decimal
    created_at: datetime
    updated_at: datetime


class OCRLineWithChildren(OCRLineRead):
    """`OCRLineRead` plus its child `OCRWord` rows — one nesting level of the
    tree `GET /ocr-results/{id}/blocks` returns."""

    words: list[OCRWordRead] = Field(default_factory=list)
