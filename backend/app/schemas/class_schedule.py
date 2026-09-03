"""ClassSchedule schemas."""

import uuid
from datetime import datetime, time
from typing import Literal

from app.schemas.base import BaseSchema

DayOfWeek = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class ClassScheduleRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    subject_allocation_id: uuid.UUID
    room_id: uuid.UUID
    day_of_week: str
    start_time: time
    end_time: time
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ClassScheduleCreate(BaseSchema):
    subject_allocation_id: uuid.UUID
    room_id: uuid.UUID
    day_of_week: DayOfWeek
    start_time: time
    end_time: time


class ClassScheduleUpdate(BaseSchema):
    subject_allocation_id: uuid.UUID | None = None
    room_id: uuid.UUID | None = None
    day_of_week: DayOfWeek | None = None
    start_time: time | None = None
    end_time: time | None = None
    is_active: bool | None = None
