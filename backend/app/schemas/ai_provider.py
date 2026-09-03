"""AIProvider schemas — global AI evaluation engine catalog (Module 06)."""

import uuid
from datetime import datetime

from app.schemas.base import BaseSchema


class AIProviderRead(BaseSchema):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    is_enabled: bool
    is_implemented: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime


class AIProviderUpdate(BaseSchema):
    """`code`/`name`/`is_implemented` are immutable after seeding — deliberately absent."""

    is_enabled: bool | None = None
    is_default: bool | None = None
