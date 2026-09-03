"""MarkDistribution schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema


class MarkDistributionRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    rubric_criterion_id: uuid.UUID
    band_name: str
    min_score: Decimal
    max_score: Decimal
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class MarkDistributionCreate(BaseSchema):
    rubric_criterion_id: uuid.UUID
    band_name: str = Field(min_length=1, max_length=100)
    min_score: Decimal = Field(ge=0)
    max_score: Decimal = Field(ge=0)
    description: str | None = None


class MarkDistributionUpdate(BaseSchema):
    band_name: str | None = Field(default=None, min_length=1, max_length=100)
    min_score: Decimal | None = Field(default=None, ge=0)
    max_score: Decimal | None = Field(default=None, ge=0)
    description: str | None = None
