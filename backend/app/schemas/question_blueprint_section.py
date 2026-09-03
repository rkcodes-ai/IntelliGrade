"""QuestionBlueprintSection schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema


class QuestionBlueprintSectionRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    blueprint_id: uuid.UUID
    question_category_id: uuid.UUID | None = None
    difficulty_level_id: uuid.UUID | None = None
    bloom_level_id: uuid.UUID | None = None
    question_type_id: uuid.UUID | None = None
    number_of_questions: int
    marks_per_question: Decimal
    display_order: int
    created_at: datetime
    updated_at: datetime


class QuestionBlueprintSectionCreate(BaseSchema):
    blueprint_id: uuid.UUID
    question_category_id: uuid.UUID | None = None
    difficulty_level_id: uuid.UUID | None = None
    bloom_level_id: uuid.UUID | None = None
    question_type_id: uuid.UUID | None = None
    number_of_questions: int = Field(gt=0)
    marks_per_question: Decimal = Field(gt=0, max_digits=6, decimal_places=2)
    display_order: int = 0


class QuestionBlueprintSectionUpdate(BaseSchema):
    blueprint_id: uuid.UUID | None = None
    question_category_id: uuid.UUID | None = None
    difficulty_level_id: uuid.UUID | None = None
    bloom_level_id: uuid.UUID | None = None
    question_type_id: uuid.UUID | None = None
    number_of_questions: int | None = Field(default=None, gt=0)
    marks_per_question: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=2)
    display_order: int | None = None
