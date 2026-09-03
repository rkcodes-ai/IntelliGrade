"""QuestionPaperVersion schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.base import BaseSchema


class QuestionPaperVersionRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    question_paper_id: uuid.UUID
    version_number: int
    snapshot: dict[str, Any]
    change_reason: str | None = None
    changed_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class QuestionPaperVersionSnapshotRequest(BaseSchema):
    """Body of `POST /question-papers/{id}/versions` — the snapshot content
    itself and `version_number` are computed server-side."""

    change_reason: str | None = Field(default=None, max_length=2000)
