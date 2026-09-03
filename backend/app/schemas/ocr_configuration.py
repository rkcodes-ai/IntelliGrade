"""OCRConfiguration schemas — per-assessment (or institution-wide) OCR settings (Module 05)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema


class OCRConfigurationRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    assessment_id: uuid.UUID | None = None
    ocr_provider_id: uuid.UUID
    language: str
    confidence_threshold: Decimal | None = None
    preprocessing_steps: list[str] | None = None
    max_retry_attempts: int
    is_active: bool
    # Ensemble Mode (Six-Provider OCR milestone) — opt-in, off by default.
    is_ensemble_enabled: bool
    ensemble_provider_codes: list[str] | None = None
    created_at: datetime
    updated_at: datetime


class OCRConfigurationCreate(BaseSchema):
    """`assessment_id` omitted (or `null`) means an institution-wide default."""

    assessment_id: uuid.UUID | None = None
    ocr_provider_id: uuid.UUID
    language: str = Field(default="eng", min_length=1, max_length=10)
    confidence_threshold: Decimal | None = Field(default=None, ge=0, le=100)
    preprocessing_steps: list[str] | None = None
    max_retry_attempts: int = Field(default=3, ge=0)
    is_ensemble_enabled: bool = False
    ensemble_provider_codes: list[str] | None = None


class OCRConfigurationUpdate(BaseSchema):
    """`assessment_id`/`ocr_provider_id` are immutable after creation — deliberately absent."""

    language: str | None = Field(default=None, min_length=1, max_length=10)
    confidence_threshold: Decimal | None = Field(default=None, ge=0, le=100)
    preprocessing_steps: list[str] | None = None
    max_retry_attempts: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    is_ensemble_enabled: bool | None = None
    ensemble_provider_codes: list[str] | None = None
