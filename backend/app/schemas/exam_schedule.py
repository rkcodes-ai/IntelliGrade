"""ExamSchedule schemas."""

import uuid
from datetime import datetime

from app.schemas.base import BaseSchema


class ExamScheduleRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    exam_id: uuid.UUID
    room_id: uuid.UUID | None = None
    start_time: datetime
    end_time: datetime
    invigilator_user_id: uuid.UUID | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ExamScheduleCreate(BaseSchema):
    exam_id: uuid.UUID
    room_id: uuid.UUID | None = None
    start_time: datetime
    end_time: datetime
    invigilator_user_id: uuid.UUID | None = None


class ExamScheduleUpdate(BaseSchema):
    exam_id: uuid.UUID | None = None
    room_id: uuid.UUID | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    invigilator_user_id: uuid.UUID | None = None
    is_active: bool | None = None
