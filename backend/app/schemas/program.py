"""Program schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema

DegreeType = Literal["ug", "pg", "diploma", "doctorate", "certificate"]


class ProgramRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    department_id: uuid.UUID
    name: str
    code: str
    degree_type: str
    duration_years: int
    total_semesters: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProgramCreate(BaseSchema):
    department_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    degree_type: DegreeType
    duration_years: int = Field(ge=1, le=10)
    total_semesters: int = Field(ge=1, le=20)


class ProgramUpdate(BaseSchema):
    department_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    degree_type: DegreeType | None = None
    duration_years: int | None = Field(default=None, ge=1, le=10)
    total_semesters: int | None = Field(default=None, ge=1, le=20)
    is_active: bool | None = None
