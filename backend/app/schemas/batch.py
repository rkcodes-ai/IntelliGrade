"""Batch schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class BatchRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    course_id: uuid.UUID
    name: str
    start_year: int
    end_year: int
    current_semester_number: int | None = None
    max_strength: int | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BatchCreate(BaseSchema):
    course_id: uuid.UUID
    name: str = Field(min_length=1, max_length=50)
    start_year: int = Field(ge=1900, le=3000)
    end_year: int = Field(ge=1900, le=3000)
    current_semester_number: int | None = Field(default=1, ge=1, le=20)
    max_strength: int | None = Field(default=None, ge=1)


class BatchUpdate(BaseSchema):
    course_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=50)
    start_year: int | None = Field(default=None, ge=1900, le=3000)
    end_year: int | None = Field(default=None, ge=1900, le=3000)
    current_semester_number: int | None = Field(default=None, ge=1, le=20)
    max_strength: int | None = Field(default=None, ge=1)
    is_active: bool | None = None
