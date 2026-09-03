"""AssessmentConfiguration schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from app.schemas.base import BaseSchema


class AssessmentConfigurationRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    assessment_id: uuid.UUID
    maximum_marks: Decimal
    passing_marks: Decimal
    negative_marks: Decimal | None = None
    grace_marks: Decimal | None = None
    time_limit_minutes: int | None = None
    attempt_rules: dict[str, Any] | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AssessmentConfigurationCreate(BaseSchema):
    assessment_id: uuid.UUID
    maximum_marks: Decimal = Field(gt=0)
    passing_marks: Decimal = Field(gt=0)
    negative_marks: Decimal | None = Field(default=Decimal("0"), ge=0)
    grace_marks: Decimal | None = Field(default=Decimal("0"), ge=0)
    time_limit_minutes: int | None = Field(default=None, gt=0)
    attempt_rules: dict[str, Any] | None = None


class AssessmentConfigurationUpdate(BaseSchema):
    maximum_marks: Decimal | None = Field(default=None, gt=0)
    passing_marks: Decimal | None = Field(default=None, gt=0)
    negative_marks: Decimal | None = Field(default=None, ge=0)
    grace_marks: Decimal | None = Field(default=None, ge=0)
    time_limit_minutes: int | None = Field(default=None, gt=0)
    attempt_rules: dict[str, Any] | None = None
    is_active: bool | None = None
