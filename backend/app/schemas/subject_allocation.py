"""SubjectAllocation schemas."""

import uuid
from datetime import datetime

from app.schemas.base import BaseSchema


class SubjectAllocationRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    subject_id: uuid.UUID
    section_id: uuid.UUID
    semester_id: uuid.UUID
    academic_year_id: uuid.UUID
    teacher_user_id: uuid.UUID
    room_id: uuid.UUID | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SubjectAllocationCreate(BaseSchema):
    subject_id: uuid.UUID
    section_id: uuid.UUID
    semester_id: uuid.UUID
    academic_year_id: uuid.UUID
    teacher_user_id: uuid.UUID
    room_id: uuid.UUID | None = None


class SubjectAllocationUpdate(BaseSchema):
    subject_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    semester_id: uuid.UUID | None = None
    academic_year_id: uuid.UUID | None = None
    teacher_user_id: uuid.UUID | None = None
    room_id: uuid.UUID | None = None
    is_active: bool | None = None
