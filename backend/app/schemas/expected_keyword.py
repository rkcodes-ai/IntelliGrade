"""ExpectedKeyword schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema


class ExpectedKeywordRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    answer_key_id: uuid.UUID | None = None
    rubric_criterion_id: uuid.UUID | None = None
    keyword: str
    weight: Decimal | None = None
    is_mandatory: bool
    created_at: datetime
    updated_at: datetime


class ExpectedKeywordCreate(BaseSchema):
    answer_key_id: uuid.UUID | None = None
    rubric_criterion_id: uuid.UUID | None = None
    keyword: str = Field(min_length=1, max_length=200)
    weight: Decimal | None = Field(default=Decimal("1.0"), ge=0)
    is_mandatory: bool = False


class ExpectedKeywordUpdate(BaseSchema):
    answer_key_id: uuid.UUID | None = None
    rubric_criterion_id: uuid.UUID | None = None
    keyword: str | None = Field(default=None, min_length=1, max_length=200)
    weight: Decimal | None = Field(default=None, ge=0)
    is_mandatory: bool | None = None
