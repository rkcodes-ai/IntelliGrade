"""OCRWord schemas — one recognized word within an OCRLine (Module 05)."""

import uuid
from datetime import datetime
from decimal import Decimal

from app.schemas.base import BaseSchema


class OCRWordRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    ocr_line_id: uuid.UUID
    text: str
    reading_order: int
    bbox_left: int
    bbox_top: int
    bbox_width: int
    bbox_height: int
    confidence: Decimal
    created_at: datetime
    updated_at: datetime
