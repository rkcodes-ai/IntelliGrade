"""ExamInstructions schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class ExamInstructionsRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    exam_id: uuid.UUID
    instructions_text: str
    display_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ExamInstructionsCreate(BaseSchema):
    exam_id: uuid.UUID
    instructions_text: str = Field(min_length=1)
    display_order: int = 0


class ExamInstructionsUpdate(BaseSchema):
    exam_id: uuid.UUID | None = None
    instructions_text: str | None = Field(default=None, min_length=1)
    display_order: int | None = None
    is_active: bool | None = None
