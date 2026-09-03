"""QuestionTag schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class QuestionTagRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    name: str
    description: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class QuestionTagCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class QuestionTagUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    is_active: bool | None = None
