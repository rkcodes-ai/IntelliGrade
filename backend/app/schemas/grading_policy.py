"""GradingPolicy schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.base import BaseSchema

GradingScale = Literal["percentage", "gpa_4", "gpa_10", "letter"]


class GradingPolicyRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    program_id: uuid.UUID | None = None
    name: str
    grading_scale: str
    passing_criteria: dict[str, Any]
    grade_bands: list[dict[str, Any]]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class GradingPolicyCreate(BaseSchema):
    program_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    grading_scale: GradingScale
    passing_criteria: dict[str, Any] = Field(default_factory=dict)
    grade_bands: list[dict[str, Any]] = Field(default_factory=list)


class GradingPolicyUpdate(BaseSchema):
    program_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    grading_scale: GradingScale | None = None
    passing_criteria: dict[str, Any] | None = None
    grade_bands: list[dict[str, Any]] | None = None
    is_active: bool | None = None
