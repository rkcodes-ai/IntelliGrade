"""MarkSchemeRange schemas — one question-range -> marks-per-question row
from a mark_scheme-type `OfficialExamDocument` (Module 06)."""

import uuid
from datetime import datetime
from decimal import Decimal

from app.schemas.base import BaseSchema


class MarkSchemeRangeRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    document_id: uuid.UUID
    question_range_start: str
    question_range_end: str
    marks_per_question: Decimal
    display_order: int
    verification_status: str
    verified_by: uuid.UUID | None = None
    verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MarkSchemeRangeUpdate(BaseSchema):
    """Rows are written internally by the ingestion pipeline; a teacher may
    only correct the range bounds/marks/ordering — never
    `verification_status`/`verified_by`/`verified_at`, which are managed
    exclusively by the `/verify` action."""

    question_range_start: str | None = None
    question_range_end: str | None = None
    marks_per_question: Decimal | None = None
    display_order: int | None = None


class MarkSchemeExpansionResponse(BaseSchema):
    """Mirrors `app.services.mark_scheme_service.MarkSchemeExpansionResult`'s
    shape for the API response."""

    marks_by_question: dict[str, Decimal]
    warnings: list[str]
