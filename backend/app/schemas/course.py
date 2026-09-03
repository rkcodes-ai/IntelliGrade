"""Course schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class CourseRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    program_id: uuid.UUID
    name: str
    code: str
    description: str | None = None
    duration_years: int | None = None
    total_semesters: int | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CourseCreate(BaseSchema):
    program_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    description: str | None = None
    duration_years: int | None = Field(default=None, ge=1, le=10)
    total_semesters: int | None = Field(default=None, ge=1, le=20)


class CourseUpdate(BaseSchema):
    program_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    description: str | None = None
    duration_years: int | None = Field(default=None, ge=1, le=10)
    total_semesters: int | None = Field(default=None, ge=1, le=20)
    is_active: bool | None = None
