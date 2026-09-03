"""Rubric schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema


class RubricRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    question_id: uuid.UUID | None = None
    name: str
    total_marks: Decimal
    is_active: bool
    current_version: int
    created_at: datetime
    updated_at: datetime


class RubricCreate(BaseSchema):
    question_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    total_marks: Decimal = Field(gt=0)


class RubricUpdate(BaseSchema):
    question_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    total_marks: Decimal | None = Field(default=None, gt=0)
    is_active: bool | None = None
