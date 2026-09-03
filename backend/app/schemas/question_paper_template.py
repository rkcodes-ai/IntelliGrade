"""QuestionPaperTemplate schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class QuestionPaperTemplateRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    name: str
    description: str | None = None
    header_text: str | None = None
    footer_text: str | None = None
    instructions_text: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class QuestionPaperTemplateCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    header_text: str | None = None
    footer_text: str | None = None
    instructions_text: str | None = None


class QuestionPaperTemplateUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    header_text: str | None = None
    footer_text: str | None = None
    instructions_text: str | None = None
    is_active: bool | None = None
