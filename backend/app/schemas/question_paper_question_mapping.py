"""QuestionPaperQuestionMapping schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema


class QuestionPaperQuestionMappingRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    question_paper_section_id: uuid.UUID
    question_id: uuid.UUID
    order_index: int
    marks_override: Decimal | None = None
    is_optional: bool
    created_at: datetime
    updated_at: datetime


class QuestionPaperQuestionMappingCreate(BaseSchema):
    question_paper_section_id: uuid.UUID
    question_id: uuid.UUID
    order_index: int = Field(default=0, ge=0)
    marks_override: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=2)
    is_optional: bool = False


class QuestionPaperQuestionMappingUpdate(BaseSchema):
    question_paper_section_id: uuid.UUID | None = None
    question_id: uuid.UUID | None = None
    order_index: int | None = Field(default=None, ge=0)
    marks_override: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=2)
    is_optional: bool | None = None
