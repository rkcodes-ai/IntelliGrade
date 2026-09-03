"""AIConfiguration schemas — per-assessment (or institution-wide) AI evaluation provider
selection (Module 06)."""

import uuid
from datetime import datetime
from typing import Any

from app.schemas.base import BaseSchema


class AIConfigurationRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    assessment_id: uuid.UUID | None = None
    ai_provider_id: uuid.UUID
    provider_config: dict[str, Any] | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AIConfigurationCreate(BaseSchema):
    """`assessment_id` omitted (or `null`) means an institution-wide default."""

    assessment_id: uuid.UUID | None = None
    ai_provider_id: uuid.UUID
    provider_config: dict[str, Any] | None = None
    is_active: bool = True


class AIConfigurationUpdate(BaseSchema):
    """`assessment_id`/`ai_provider_id` are immutable after creation — deliberately absent."""

    provider_config: dict[str, Any] | None = None
    is_active: bool | None = None
