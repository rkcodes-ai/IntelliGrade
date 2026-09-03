"""QuestionVersion schemas — append-only snapshot history for `Question`."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema


class QuestionVersionRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    question_id: uuid.UUID
    version_number: int
    question_text: str
    marks: Decimal
    difficulty_level_id: uuid.UUID
    change_reason: str | None = None
    changed_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class QuestionVersionSnapshotRequest(BaseSchema):
    """
    Body for `POST /api/v1/questions/{question_id}/versions`
    (`app/api/v1/endpoints/questions.py`) — the only way a `QuestionVersion`
    row is ever created. There is deliberately no generic
    `QuestionVersionCreate`/`QuestionVersionUpdate` schema: this table is
    populated exclusively by `QuestionVersionService.create_snapshot`, never
    directly by a client-supplied full payload.
    """

    change_reason: str | None = Field(default=None, max_length=2000)
