"""QuestionApproval schemas — the formal approve/reject decision audit trail for `Question`."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema

#: Mirrors `QuestionApproval.decision`'s plain-string column (no DB CHECK
#: constraint, see `app/models/question_approval.py`'s docstring).
ApprovalDecision = Literal["approved", "rejected"]


class QuestionApprovalRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    question_id: uuid.UUID
    question_version_id: uuid.UUID | None = None
    decision: ApprovalDecision
    reviewed_by: uuid.UUID | None = None
    reviewed_at: datetime
    comments: str | None = None
    created_at: datetime
    updated_at: datetime


class QuestionApprovalCreate(BaseSchema):
    """
    Used by `QuestionApprovalService.create()` (callable directly by anyone
    holding `QUESTION_APPROVALS_CREATE`); there is currently no `POST
    /api/v1/question-approvals` HTTP endpoint wired to it — see
    `app/api/v1/endpoints/question_approvals.py`'s module docstring.
    `reviewed_by` is never part of the body — the caller supplies it as an
    explicit keyword argument (the authenticated reviewer), never trusted
    from client input.
    """

    question_id: uuid.UUID
    question_version_id: uuid.UUID | None = None
    decision: ApprovalDecision
    comments: str | None = Field(default=None, max_length=4000)
