"""OCRProvider schemas — global OCR engine catalog (Module 05)."""

import uuid
from datetime import datetime

from app.schemas.base import BaseSchema


class OCRProviderRead(BaseSchema):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    is_enabled: bool
    is_implemented: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime


class OCRProviderUpdate(BaseSchema):
    """`code`/`name`/`is_implemented` are immutable after seeding — deliberately absent."""

    is_enabled: bool | None = None
    is_default: bool | None = None


class OCRProviderHealthRead(BaseSchema):
    """Mirrors `app.services.ocr.models.HealthCheckResult` — live, on-demand
    engine health, never persisted (see `GET /ocr-providers/{id}/health`)."""

    provider_code: str
    installed: bool
    version: str | None = None
    configured: bool
    authenticated: bool | None = None
    connectivity: bool | None = None
    dependencies_ok: bool
    gpu_available: bool | None = None
    ready: bool
    detail: str | None = None
