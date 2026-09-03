"""AlternativeAnswer schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class AlternativeAnswerRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    answer_key_id: uuid.UUID
    content: str
    is_exact_match: bool
    created_at: datetime
    updated_at: datetime


class AlternativeAnswerCreate(BaseSchema):
    answer_key_id: uuid.UUID
    content: str = Field(min_length=1)
    is_exact_match: bool = False


class AlternativeAnswerUpdate(BaseSchema):
    """Deliberately excludes `answer_key_id` — the parent link is fixed at creation."""

    content: str | None = Field(default=None, min_length=1)
    is_exact_match: bool | None = None
