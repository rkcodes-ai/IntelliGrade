"""ModelAnswer schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema


class ModelAnswerRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    answer_key_id: uuid.UUID
    content: str
    marks_allocated: Decimal | None = None
    display_order: int
    created_at: datetime
    updated_at: datetime


class ModelAnswerCreate(BaseSchema):
    answer_key_id: uuid.UUID
    content: str = Field(min_length=1)
    marks_allocated: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=2)
    display_order: int = Field(default=0, ge=0)


class ModelAnswerUpdate(BaseSchema):
    """Deliberately excludes `answer_key_id` — the parent link is fixed at creation."""

    content: str | None = Field(default=None, min_length=1)
    marks_allocated: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=2)
    display_order: int | None = Field(default=None, ge=0)
