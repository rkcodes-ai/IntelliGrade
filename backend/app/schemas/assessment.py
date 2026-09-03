"""Assessment schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class AssessmentRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    subject_id: uuid.UUID
    assessment_type_id: uuid.UUID
    assessment_status_id: uuid.UUID
    name: str
    description: str | None = None
    is_active: bool
    current_version: int
    created_at: datetime
    updated_at: datetime


class AssessmentCreate(BaseSchema):
    subject_id: uuid.UUID
    assessment_type_id: uuid.UUID
    assessment_status_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class AssessmentUpdate(BaseSchema):
    subject_id: uuid.UUID | None = None
    assessment_type_id: uuid.UUID | None = None
    assessment_status_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    is_active: bool | None = None
