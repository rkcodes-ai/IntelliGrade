"""OCRBlock schemas — one layout block within an OCRResult (Module 05)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema
from app.schemas.ocr_line import OCRLineWithChildren

#: Mirrors `OCRBlock.block_type`'s plain-string column (no DB CHECK
#: constraint, see `app/models/ocr_block.py`'s docstring).
OCRBlockType = Literal["text", "table", "image"]


class OCRBlockRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    ocr_result_id: uuid.UUID
    block_type: OCRBlockType
    reading_order: int
    bbox_left: int
    bbox_top: int
    bbox_width: int
    bbox_height: int
    confidence: Decimal
    created_at: datetime
    updated_at: datetime


class OCRBlockWithChildren(OCRBlockRead):
    """`OCRBlockRead` plus its child `OCRLine` rows (each with their own
    child `OCRWord` rows) — the full nested tree `GET
    /ocr-results/{id}/blocks` returns for the frontend's OCR Text Viewer /
    bounding-box overlay."""

    lines: list[OCRLineWithChildren] = Field(default_factory=list)
