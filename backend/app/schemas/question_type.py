"""QuestionType schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class QuestionTypeRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    requires_options: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class QuestionTypeCreate(BaseSchema):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    requires_options: bool = False


class QuestionTypeUpdate(BaseSchema):
    code: str | None = Field(default=None, min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    requires_options: bool | None = None
    is_active: bool | None = None
