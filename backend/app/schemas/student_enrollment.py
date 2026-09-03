"""StudentEnrollment schemas."""

import uuid
from datetime import date, datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class StudentEnrollmentRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    student_user_id: uuid.UUID
    batch_id: uuid.UUID
    section_id: uuid.UUID
    course_id: uuid.UUID
    academic_year_id: uuid.UUID
    semester_id: uuid.UUID
    academic_status_id: uuid.UUID
    roll_number: str
    enrollment_date: date
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StudentEnrollmentCreate(BaseSchema):
    student_user_id: uuid.UUID
    batch_id: uuid.UUID
    section_id: uuid.UUID
    course_id: uuid.UUID
    academic_year_id: uuid.UUID
    semester_id: uuid.UUID
    academic_status_id: uuid.UUID
    roll_number: str = Field(min_length=1, max_length=32)
    enrollment_date: date


class StudentEnrollmentUpdate(BaseSchema):
    student_user_id: uuid.UUID | None = None
    batch_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    course_id: uuid.UUID | None = None
    academic_year_id: uuid.UUID | None = None
    semester_id: uuid.UUID | None = None
    academic_status_id: uuid.UUID | None = None
    roll_number: str | None = Field(default=None, min_length=1, max_length=32)
    enrollment_date: date | None = None
    is_active: bool | None = None


class StudentEnrollmentStatusChange(BaseSchema):
    new_status_id: uuid.UUID
