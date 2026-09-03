"""AcademicCalendarEvent schemas."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema

EventType = Literal["holiday", "exam", "registration", "orientation", "other"]


class AcademicCalendarEventRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    academic_year_id: uuid.UUID
    title: str
    event_type: str
    start_date: date
    end_date: date
    description: str | None = None
    is_holiday: bool
    created_at: datetime
    updated_at: datetime


class AcademicCalendarEventCreate(BaseSchema):
    academic_year_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    event_type: EventType
    start_date: date
    end_date: date
    description: str | None = None
    is_holiday: bool = False


class AcademicCalendarEventUpdate(BaseSchema):
    academic_year_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    event_type: EventType | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None
    is_holiday: bool | None = None
