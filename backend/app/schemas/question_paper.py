"""QuestionPaper schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema

#: Mirrors `ApprovalWorkflowMixin`'s draft -> pending_review ->
#: approved/rejected -> archived lifecycle — same idiom as
#: `app/schemas/question.py`'s `ApprovalStatus`.
ApprovalStatus = Literal["draft", "pending_review", "approved", "rejected", "archived"]


class QuestionPaperRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    assessment_id: uuid.UUID
    blueprint_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    name: str
    total_marks: Decimal
    is_active: bool
    current_version: int
    approval_status: ApprovalStatus
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class QuestionPaperCreate(BaseSchema):
    assessment_id: uuid.UUID
    blueprint_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    total_marks: Decimal = Field(gt=0, max_digits=6, decimal_places=2)


class QuestionPaperUpdate(BaseSchema):
    """
    Deliberately excludes `approval_status`/`approved_by`/`approved_at`/
    `rejection_reason` — those transition only through the dedicated
    `/submit-for-review`, `/approve`, `/reject` endpoints
    (`app/api/v1/endpoints/question_papers.py`), never via a generic PATCH,
    exactly like `app/schemas/question.py`'s `QuestionUpdate`.
    """

    assessment_id: uuid.UUID | None = None
    blueprint_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    total_marks: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=2)
    is_active: bool | None = None


class QuestionPaperRejectRequest(BaseSchema):
    reason: str = Field(min_length=1)
