"""AcademicYear schemas."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema

AcademicYearStatus = Literal["planned", "active", "completed", "archived"]


class AcademicYearRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    year_label: str
    start_date: date
    end_date: date
    is_current: bool
    status: str
    created_at: datetime
    updated_at: datetime


class AcademicYearCreate(BaseSchema):
    year_label: str = Field(min_length=1, max_length=20)
    start_date: date
    end_date: date
    is_current: bool = False
    status: AcademicYearStatus = "planned"


class AcademicYearUpdate(BaseSchema):
    year_label: str | None = Field(default=None, min_length=1, max_length=20)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None
    status: AcademicYearStatus | None = None
