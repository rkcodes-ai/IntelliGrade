"""TeacherAssignment schemas."""

import uuid
from datetime import date, datetime
from typing import Literal

from app.schemas.base import BaseSchema

AssignmentRole = Literal["primary", "assistant", "substitute"]


class TeacherAssignmentRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    teacher_user_id: uuid.UUID
    subject_allocation_id: uuid.UUID
    assignment_role: str
    assigned_from: date
    assigned_to: date | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TeacherAssignmentCreate(BaseSchema):
    teacher_user_id: uuid.UUID
    subject_allocation_id: uuid.UUID
    assignment_role: AssignmentRole = "primary"
    assigned_from: date
    assigned_to: date | None = None


class TeacherAssignmentUpdate(BaseSchema):
    teacher_user_id: uuid.UUID | None = None
    subject_allocation_id: uuid.UUID | None = None
    assignment_role: AssignmentRole | None = None
    assigned_from: date | None = None
    assigned_to: date | None = None
    is_active: bool | None = None
