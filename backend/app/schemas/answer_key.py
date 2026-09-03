"""AnswerKey schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from app.schemas.base import BaseSchema


class AnswerKeyRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    question_id: uuid.UUID
    reference_answer: str
    expected_length: int | None = None
    expected_structure: dict[str, Any] | None = None
    confidence_threshold: Decimal | None = None
    ai_config: dict[str, Any] | None = None
    evaluation_notes: str | None = None
    current_version: int
    created_at: datetime
    updated_at: datetime


class AnswerKeyCreate(BaseSchema):
    question_id: uuid.UUID
    reference_answer: str = Field(min_length=1)
    expected_length: int | None = Field(default=None, ge=0)
    expected_structure: dict[str, Any] | None = None
    # AI-preparation placeholder per ADR-024 — not used by any code yet.
    confidence_threshold: Decimal | None = Field(
        default=None, ge=0, le=1, max_digits=4, decimal_places=3
    )
    # AI-preparation placeholder per ADR-024 — not used by any code yet.
    ai_config: dict[str, Any] | None = None
    evaluation_notes: str | None = None


class AnswerKeyUpdate(BaseSchema):
    """
    Deliberately excludes `question_id` — the 1:1 link to its `Question` is
    fixed at creation, same as `AssessmentConfigurationUpdate` excluding
    `assessment_id` (`app/schemas/assessment_configuration.py`).
    """

    reference_answer: str | None = Field(default=None, min_length=1)
    expected_length: int | None = Field(default=None, ge=0)
    expected_structure: dict[str, Any] | None = None
    confidence_threshold: Decimal | None = Field(
        default=None, ge=0, le=1, max_digits=4, decimal_places=3
    )
    ai_config: dict[str, Any] | None = None
    evaluation_notes: str | None = None
