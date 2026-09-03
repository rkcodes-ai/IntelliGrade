"""EvaluationConfiguration schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field

from app.schemas.base import BaseSchema

EvaluationMode = Literal["manual", "auto", "hybrid"]


class EvaluationConfigurationRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    assessment_id: uuid.UUID
    evaluation_mode: str
    confidence_threshold: Decimal | None = None
    ai_config: dict[str, Any] | None = None
    auto_publish_results: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class EvaluationConfigurationCreate(BaseSchema):
    assessment_id: uuid.UUID
    evaluation_mode: EvaluationMode
    confidence_threshold: Decimal | None = Field(default=None, ge=0, le=1)
    ai_config: dict[str, Any] | None = None
    auto_publish_results: bool = False


class EvaluationConfigurationUpdate(BaseSchema):
    evaluation_mode: EvaluationMode | None = None
    confidence_threshold: Decimal | None = Field(default=None, ge=0, le=1)
    ai_config: dict[str, Any] | None = None
    auto_publish_results: bool | None = None
    is_active: bool | None = None
