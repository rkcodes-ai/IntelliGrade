"""ExamSession schemas."""

import uuid
from datetime import datetime
from typing import Literal

from app.schemas.base import BaseSchema

ExamSessionStatus = Literal["not_started", "in_progress", "submitted", "evaluated", "absent"]


class ExamSessionRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    exam_id: uuid.UUID
    student_user_id: uuid.UUID
    status: ExamSessionStatus
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ExamSessionCreate(BaseSchema):
    exam_id: uuid.UUID
    student_user_id: uuid.UUID
    status: ExamSessionStatus = "not_started"
    started_at: datetime | None = None
    submitted_at: datetime | None = None


class ExamSessionUpdate(BaseSchema):
    exam_id: uuid.UUID | None = None
    student_user_id: uuid.UUID | None = None
    status: ExamSessionStatus | None = None
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    is_active: bool | None = None
