"""ProcessingHistory schemas — append-only per-stage transition log for an AnswerScript."""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import Query

from app.schemas.base import BaseSchema
from app.schemas.pagination import MAX_PAGE_SIZE, PageParams, SortOrder

#: Mirrors `ProcessingHistory.triggered_by`'s plain-string column (no DB
#: CHECK constraint, see `app/models/processing_history.py`'s docstring).
TriggeredBy = Literal["system", "user", "retry"]


class ProcessingHistoryRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    answer_script_id: uuid.UUID
    stage: str
    from_status: str | None = None
    to_status: str
    duration_ms: int | None = None
    error_detail: str | None = None
    triggered_by: TriggeredBy
    created_at: datetime
    updated_at: datetime


class ProcessingHistoryListParams(PageParams):
    """
    `PageParams` plus an optional `answer_script_id` filter.

    No existing precedent in this codebase for a single-FK list filter was
    found (the only `class .*Params` in `app/schemas/` is `PageParams`
    itself), so this is a minimal, entity-local subclass rather than a
    change to the shared `app/schemas/pagination.py`.
    """

    def __init__(
        self,
        page: int = Query(default=1, ge=1, description="1-indexed page number"),
        page_size: int = Query(default=25, ge=1, le=MAX_PAGE_SIZE),
        search: str | None = Query(default=None, max_length=200),
        sort_by: str | None = Query(default=None, max_length=64),
        sort_order: SortOrder = Query(default=SortOrder.ASC),
        answer_script_id: uuid.UUID | None = Query(
            default=None, description="Filter to a single answer script's history."
        ),
    ) -> None:
        super().__init__(
            page=page,
            page_size=page_size,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        self.answer_script_id = answer_script_id
