"""QuestionBlueprint schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema


class QuestionBlueprintRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    subject_id: uuid.UUID
    name: str
    total_marks: Decimal
    total_questions: int
    is_active: bool
    current_version: int
    created_at: datetime
    updated_at: datetime


class QuestionBlueprintCreate(BaseSchema):
    subject_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    total_marks: Decimal = Field(gt=0, max_digits=6, decimal_places=2)
    total_questions: int = Field(gt=0)


class QuestionBlueprintUpdate(BaseSchema):
    subject_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    total_marks: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=2)
    total_questions: int | None = Field(default=None, gt=0)
    is_active: bool | None = None
