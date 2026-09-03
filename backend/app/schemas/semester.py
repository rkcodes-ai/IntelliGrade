"""Semester schemas."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema

SemesterTermType = Literal["odd", "even"]
SemesterStatus = Literal["planned", "active", "completed", "archived"]


class SemesterRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    academic_year_id: uuid.UUID
    name: str
    semester_number: int
    term_type: str
    start_date: date
    end_date: date
    status: str
    created_at: datetime
    updated_at: datetime


class SemesterCreate(BaseSchema):
    academic_year_id: uuid.UUID
    name: str = Field(min_length=1, max_length=100)
    semester_number: int = Field(ge=1, le=20)
    term_type: SemesterTermType
    start_date: date
    end_date: date
    status: SemesterStatus = "planned"


class SemesterUpdate(BaseSchema):
    academic_year_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    semester_number: int | None = Field(default=None, ge=1, le=20)
    term_type: SemesterTermType | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: SemesterStatus | None = None
