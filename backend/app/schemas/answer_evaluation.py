"""AnswerEvaluation schemas.

No client-facing `Create` schema: rows are written internally by
`AnswerEvaluationService.evaluate_question()`, never accepted as an
arbitrary client-supplied payload — a client-forgeable AI evaluation
result would be meaningless. `AnswerEvaluationOverride` is the only
client-facing write, for the teacher-review "override" action.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from app.schemas.base import BaseSchema

ConfidenceTier = Literal["high", "medium", "low"]
ReviewStatus = Literal[
    "auto_suggested",
    "pending_confirmation",
    "pending_review",
    "teacher_confirmed",
    "teacher_overridden",
    "teacher_rejected",
]


class AnswerEvaluationRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    exam_session_id: uuid.UUID
    answer_script_id: uuid.UUID
    extracted_question_id: uuid.UUID
    extracted_model_answer_id: uuid.UUID | None = None
    ai_provider_id: uuid.UUID
    ai_reference_answer_id: uuid.UUID | None = None
    used_legacy_reference: bool
    student_answer_text: str | None = None
    semantic_similarity_score: Decimal | None = None
    keyword_match_score: Decimal | None = None
    concept_match_score: Decimal | None = None
    reasoning_score: Decimal | None = None
    completeness_score: Decimal | None = None
    relevance_score: Decimal | None = None
    confidence_score: Decimal | None = None
    confidence_tier: ConfidenceTier | None = None
    max_marks: Decimal
    suggested_marks: Decimal | None = None
    final_marks: Decimal | None = None
    review_status: ReviewStatus
    evaluated_at: datetime | None = None
    reviewed_by: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class AnswerEvaluationOverride(BaseSchema):
    final_marks: Decimal
    notes: str | None = None


class AnswerEvaluationReject(BaseSchema):
    """Request body for `POST /{id}/reject` (Module 07, ADR-043). `reason`
    is required — unlike an override, a rejection has no replacement marks
    of its own, so the reason is the only record of why this evaluation
    was discarded."""

    reason: str


class AnswerEvaluationTrigger(BaseSchema):
    """Request body for `POST /answer-evaluations` — triggers
    `AnswerEvaluationService.evaluate_question()` for one (student answer
    x extracted question) pair. Not a raw `Create` schema: every other
    field on `AnswerEvaluation` is computed by the AI provider, never
    client-supplied."""

    exam_session_id: uuid.UUID
    extracted_question_id: uuid.UUID
