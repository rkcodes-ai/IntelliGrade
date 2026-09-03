"""QuestionPaperSection schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema


class QuestionPaperSectionRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    question_paper_id: uuid.UUID
    name: str
    instructions: str | None = None
    marks_per_question: Decimal | None = None
    display_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class QuestionPaperSectionCreate(BaseSchema):
    question_paper_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    instructions: str | None = None
    marks_per_question: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=2)
    display_order: int = Field(default=0, ge=0)


class QuestionPaperSectionUpdate(BaseSchema):
    question_paper_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    instructions: str | None = None
    marks_per_question: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=2)
    display_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
