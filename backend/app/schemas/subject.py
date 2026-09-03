"""Subject schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema


class SubjectRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    course_id: uuid.UUID
    subject_category_id: uuid.UUID
    code: str
    name: str
    credits: Decimal
    semester_number: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SubjectCreate(BaseSchema):
    course_id: uuid.UUID
    subject_category_id: uuid.UUID
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    credits: Decimal = Field(gt=0)
    semester_number: int = Field(ge=1, le=20)


class SubjectUpdate(BaseSchema):
    course_id: uuid.UUID | None = None
    subject_category_id: uuid.UUID | None = None
    code: str | None = Field(default=None, min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    credits: Decimal | None = Field(default=None, gt=0)
    semester_number: int | None = Field(default=None, ge=1, le=20)
    is_active: bool | None = None
