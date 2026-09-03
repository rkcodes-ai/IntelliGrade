"""RubricCriterion schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema


class RubricCriterionRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    rubric_id: uuid.UUID
    parent_criterion_id: uuid.UUID | None = None
    name: str
    weightage_percent: Decimal | None = None
    max_marks: Decimal
    is_mandatory: bool
    teacher_notes: str | None = None
    ai_notes: str | None = None
    display_order: int
    is_language_criterion: bool
    created_at: datetime
    updated_at: datetime


class RubricCriterionCreate(BaseSchema):
    rubric_id: uuid.UUID
    parent_criterion_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    weightage_percent: Decimal | None = Field(default=None, ge=0, le=100)
    max_marks: Decimal = Field(gt=0)
    is_mandatory: bool = True
    teacher_notes: str | None = None
    ai_notes: str | None = None
    display_order: int = Field(default=0, ge=0)
    is_language_criterion: bool = False


class RubricCriterionUpdate(BaseSchema):
    parent_criterion_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    weightage_percent: Decimal | None = Field(default=None, ge=0, le=100)
    max_marks: Decimal | None = Field(default=None, gt=0)
    is_mandatory: bool | None = None
    teacher_notes: str | None = None
    ai_notes: str | None = None
    display_order: int | None = Field(default=None, ge=0)
    is_language_criterion: bool | None = None
