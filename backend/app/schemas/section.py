"""Section schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class SectionRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    batch_id: uuid.UUID
    name: str
    max_capacity: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SectionCreate(BaseSchema):
    batch_id: uuid.UUID
    name: str = Field(min_length=1, max_length=20)
    max_capacity: int = Field(ge=1)


class SectionUpdate(BaseSchema):
    batch_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=20)
    max_capacity: int | None = Field(default=None, ge=1)
    is_active: bool | None = None
