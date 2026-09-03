"""AIReferenceAnswer schemas (AI Reference Answer Builder milestone).

`ReferenceContentSchema` is the **structured output contract** (Phase 4):
every `AIProviderAdapter.generate_reference()` implementation must return
data that validates against this shape before it is ever persisted —
malformed AI output fails the generation attempt cleanly (`status`
becomes `generation_failed`, never a half-written or guessed row).

No client-facing `Create`/`Update` schema, same reasoning as
`AnswerEvaluation`: every content field is AI/service-generated, never an
arbitrary client-supplied payload.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field

from app.schemas.base import BaseSchema

ReferenceAnswerStatus = Literal[
    "queued", "generating", "generation_failed", "pending_verification", "approved", "rejected"
]


class ReferenceContentSchema(BaseSchema):
    """The validated shape every provider's `generate_reference()` must
    return (Phase 4). All list fields default to empty rather than being
    required — a provider that can't confidently produce a given list
    (e.g. a lexical provider has no way to invent alternative phrasings)
    must leave it empty, never fabricate entries to satisfy the schema."""

    reference_answer: str = Field(min_length=1)
    required_concepts: list[str] = Field(default_factory=list)
    optional_concepts: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    equivalent_terms: list[str] = Field(default_factory=list)
    alternative_valid_answers: list[str] = Field(default_factory=list)
    expected_reasoning: list[str] = Field(default_factory=list)
    common_misconceptions: list[str] = Field(default_factory=list)
    scoring_guidance: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=100)
    has_conflict_with_official_answer: bool = False
    conflict_notes: str | None = None

    # Step 5 milestone additions (all optional/defaulted — existing
    # OpenAI/Anthropic/LexicalHeuristic providers are unaffected):
    # `builder_metadata` records provider/model/version/timing for
    # reproducibility (Section 60); `grounding_report` is the
    # deterministic grounding-validator's own findings (Section 40/41),
    # persisted for audit even when the provider already acted on it
    # (e.g. dropped ungrounded concepts before returning this schema).
    builder_metadata: dict[str, Any] | None = None
    grounding_report: dict[str, Any] | None = None


class AIReferenceAnswerRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    extracted_question_id: uuid.UUID
    extracted_model_answer_id: uuid.UUID | None = None
    rubric_id: uuid.UUID | None = None
    ai_provider_id: uuid.UUID
    version: int
    is_current: bool
    status: ReferenceAnswerStatus
    question_text: str
    official_model_answer_text: str
    synthesized_reference_answer: str | None = None
    structured_content: dict[str, Any] | None = None
    maximum_marks: Decimal
    marks_source: str
    provider_model: str | None = None
    prompt_version: str | None = None
    generation_confidence: Decimal | None = None
    generation_error: str | None = None
    has_conflict_flag: bool
    conflict_notes: str | None = None
    rejection_reason: str | None = None
    generated_at: datetime | None = None
    verified_by: uuid.UUID | None = None
    verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AIReferenceAnswerGenerate(BaseSchema):
    """Request body for `POST /ai-reference-answers` — triggers generation
    for one `ExtractedQuestion`. `force` mirrors
    `AnswerEvaluationTrigger`/Module 05's `force` idiom: without it, a
    request against a question that already has a `pending_verification`/
    `approved` current reference is a no-op returning that row; `force`
    always creates a new version."""

    extracted_question_id: uuid.UUID
    force: bool = False


class AIReferenceAnswerReject(BaseSchema):
    reason: str = Field(min_length=1)
