"""BloomTaxonomyLevel schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class BloomTaxonomyLevelRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    code: str
    name: str
    level_order: int
    description: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BloomTaxonomyLevelCreate(BaseSchema):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    level_order: int = Field(ge=0)
    description: str | None = None


class BloomTaxonomyLevelUpdate(BaseSchema):
    code: str | None = Field(default=None, min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    name: str | None = Field(default=None, min_length=1, max_length=100)
    level_order: int | None = Field(default=None, ge=0)
    description: str | None = None
    is_active: bool | None = None
