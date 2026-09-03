"""Exam schemas."""

import uuid
from datetime import date, datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class ExamRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    assessment_id: uuid.UUID
    section_id: uuid.UUID
    name: str
    exam_date: date
    is_active: bool
    current_version: int
    created_at: datetime
    updated_at: datetime


class ExamCreate(BaseSchema):
    assessment_id: uuid.UUID
    section_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    exam_date: date


class ExamUpdate(BaseSchema):
    assessment_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    exam_date: date | None = None
    is_active: bool | None = None
