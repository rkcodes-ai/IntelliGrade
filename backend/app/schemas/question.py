"""Question and QuestionTagMap schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field

from app.schemas.base import BaseSchema

#: Mirrors `ApprovalWorkflowMixin`'s (undocumented at the DB level, see
#: `app/models/assessment_base.py`) draft -> pending_review ->
#: approved/rejected -> archived lifecycle.
ApprovalStatus = Literal["draft", "pending_review", "approved", "rejected", "archived"]


class QuestionRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    subject_id: uuid.UUID
    question_category_id: uuid.UUID
    question_type_id: uuid.UUID
    difficulty_level_id: uuid.UUID
    bloom_level_id: uuid.UUID
    unit: str | None = None
    chapter: str | None = None
    topic: str | None = None
    subtopic: str | None = None
    learning_outcome: str | None = None
    question_text: str
    estimated_time_minutes: int | None = None
    marks: Decimal
    language: str
    attachments: list[Any] | None = None
    diagram_url: str | None = None
    question_metadata: dict[str, Any] | None = None
    is_active: bool
    current_version: int
    approval_status: ApprovalStatus
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class QuestionCreate(BaseSchema):
    subject_id: uuid.UUID
    question_category_id: uuid.UUID
    question_type_id: uuid.UUID
    difficulty_level_id: uuid.UUID
    bloom_level_id: uuid.UUID
    unit: str | None = Field(default=None, max_length=200)
    chapter: str | None = Field(default=None, max_length=200)
    topic: str | None = Field(default=None, max_length=200)
    subtopic: str | None = Field(default=None, max_length=200)
    learning_outcome: str | None = None
    question_text: str = Field(min_length=1)
    estimated_time_minutes: int | None = Field(default=None, ge=0)
    marks: Decimal = Field(gt=0, max_digits=6, decimal_places=2)
    language: str = Field(default="en", min_length=1, max_length=10)
    attachments: list[Any] | None = None
    diagram_url: str | None = Field(default=None, max_length=500)
    question_metadata: dict[str, Any] | None = None


class QuestionUpdate(BaseSchema):
    """
    Deliberately excludes `approval_status`/`approved_by`/`approved_at`/
    `rejection_reason` — those transition only through the dedicated
    `/submit-for-review`, `/approve`, `/reject` endpoints
    (`app/api/v1/endpoints/questions.py`), never via a generic PATCH.
    """

    subject_id: uuid.UUID | None = None
    question_category_id: uuid.UUID | None = None
    question_type_id: uuid.UUID | None = None
    difficulty_level_id: uuid.UUID | None = None
    bloom_level_id: uuid.UUID | None = None
    unit: str | None = Field(default=None, max_length=200)
    chapter: str | None = Field(default=None, max_length=200)
    topic: str | None = Field(default=None, max_length=200)
    subtopic: str | None = Field(default=None, max_length=200)
    learning_outcome: str | None = None
    question_text: str | None = Field(default=None, min_length=1)
    estimated_time_minutes: int | None = Field(default=None, ge=0)
    marks: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=2)
    language: str | None = Field(default=None, min_length=1, max_length=10)
    attachments: list[Any] | None = None
    diagram_url: str | None = Field(default=None, max_length=500)
    question_metadata: dict[str, Any] | None = None
    is_active: bool | None = None


class QuestionRejectRequest(BaseSchema):
    reason: str = Field(min_length=1)


class QuestionTagAddRequest(BaseSchema):
    tag_id: uuid.UUID


class QuestionTagMapRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    question_id: uuid.UUID
    tag_id: uuid.UUID
    created_at: datetime
