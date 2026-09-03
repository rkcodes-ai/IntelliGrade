"""AttendancePolicy schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema


class AttendancePolicyRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    program_id: uuid.UUID | None = None
    name: str
    minimum_attendance_percentage: Decimal
    condonation_percentage: Decimal | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AttendancePolicyCreate(BaseSchema):
    program_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    minimum_attendance_percentage: Decimal = Field(ge=0, le=100)
    condonation_percentage: Decimal | None = Field(default=None, ge=0, le=100)


class AttendancePolicyUpdate(BaseSchema):
    program_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    minimum_attendance_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    condonation_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None
