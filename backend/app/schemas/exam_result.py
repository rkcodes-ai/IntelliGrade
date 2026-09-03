"""ExamResult schemas (Module 07). See ADR-042.

No client-facing `Create`/`Update` schema: rows are created and mutated
only by `ExamResultService`'s named lifecycle actions
(finalize/approve/lock/unlock/publish), never a generic CRUD write —
same "no arbitrary client-supplied payload" reasoning as
`app.schemas.answer_evaluation`.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from app.schemas.base import BaseSchema

ExamResultStatus = Literal["draft", "under_review", "approved", "locked", "published"]


class ExamResultRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    exam_session_id: uuid.UUID
    status: ExamResultStatus
    total_max_marks: Decimal | None = None
    total_marks: Decimal | None = None
    finalized_by: uuid.UUID | None = None
    finalized_at: datetime | None = None
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    locked_by: uuid.UUID | None = None
    locked_at: datetime | None = None
    published_by: uuid.UUID | None = None
    published_at: datetime | None = None
    unlocked_by: uuid.UUID | None = None
    unlocked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class FinalizeStudentRequest(BaseSchema):
    exam_session_id: uuid.UUID


class FinalizeExamRequest(BaseSchema):
    exam_id: uuid.UUID


class FinalizeBatchRequest(BaseSchema):
    exam_id: uuid.UUID
    batch_id: uuid.UUID


class BulkExamRequest(BaseSchema):
    """Body for the bulk approve/lock/publish actions — every matching
    `ExamResult` for this exam currently in the required prior status is
    transitioned; everything else is reported back, not silently skipped."""

    exam_id: uuid.UUID


class BulkActionFailure(BaseSchema):
    """`reference_id` is an `exam_session_id` for bulk finalize actions
    (no `ExamResult` row may exist yet) and an `ExamResult.id` for bulk
    approve/lock/publish actions."""

    reference_id: uuid.UUID
    reason: str


class BulkActionResult(BaseSchema):
    succeeded_count: int
    failed: list[BulkActionFailure]
