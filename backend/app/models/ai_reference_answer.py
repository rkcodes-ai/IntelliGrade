"""AIReferenceAnswer — a versioned, AI-synthesized evaluation reference for
one ExtractedQuestion (Module 06 extension). See the AI Reference Answer
Builder milestone report for the full design rationale.

**The official Model Answer remains authoritative.** This entity never
replaces `ExtractedModelAnswer` — it is an AI-expanded companion built
from it: the official answer text is frozen into
`official_model_answer_text` at generation time, and the AI is only
permitted to add structure around it (concepts, keywords, equivalent
phrasing, alternative valid answers, reasoning expectations, scoring
guidance). `has_conflict_flag`/`conflict_notes` exist specifically so a
provider that detects its own output disagreeing with the official answer
can surface that rather than silently overriding it.

**Why one JSON column, not eight.** `required_concepts`/
`optional_concepts`/`keywords`/`equivalent_terms`/
`alternative_valid_answers`/`expected_reasoning`/`common_misconceptions`/
`scoring_guidance` are generated together by one AI call, validated
together (see `app.schemas.ai_reference_answer.ReferenceContentSchema`),
versioned together, and read together by the frontend review screen — so
they live together in `structured_content`, one JSON column, same
reasoning as `AnswerScript.structured_content` (ADR-031): the shape is
AI-model-dependent and still evolving, and eight parallel columns (or
tables) would be premature relational commitment for data that is only
ever read/written as one unit. `synthesized_reference_answer` is pulled
out as its own `Text` column since it's the one field the evaluation
engine reads on every single evaluation call — worth a real column, not a
JSON lookup, for that hot path.

**Why a single `status` column, not separate generation/verification
status fields.** Every other stateful entity in this codebase
(`AnswerScript.status`, `OfficialExamDocument.ocr_status`,
`ExtractedQuestion.verification_status`, `AnswerEvaluation.review_status`)
uses one plain string lifecycle column. This follows that convention:
`queued` -> `generating` -> `generation_failed` | `pending_verification`
-> `approved` | `rejected`. `regenerate` moves an `approved`/`rejected`
row's *replacement* back to `queued` as a **new row** (new `version`) —
see `is_current`.

**Versioning.** `(extracted_question_id, version)` is unique. Exactly one
row per `extracted_question_id` has `is_current=True` at a time (enforced
at the service layer, same "at most one" idiom as `OCRProvider.is_default`
/`AIProvider.is_default`) — regenerating flips the old row to
`is_current=False` and inserts a new one; nothing is ever overwritten in
place, so a past `AnswerEvaluation.ai_reference_answer_id` always resolves
to the exact content that produced it, even after later regeneration.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AIReferenceAnswer(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    __tablename__ = "ai_reference_answers"
    __table_args__ = (
        UniqueConstraint(
            "extracted_question_id", "version", name="uq_ai_reference_answer_question_version"
        ),
    )

    # --- Anchor: the same evaluation-pipeline entity chain the just-fixed
    # Model Answer scoping bug established (ExtractedQuestion -> its
    # document -> its exam) -- deliberately NOT re-anchored to Module 04's
    # `Question`/`AnswerKey` bank, which the evaluation pipeline doesn't
    # use (see the milestone's Phase 0 audit).
    extracted_question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # `SET NULL`, not `CASCADE`: if the source model answer row is later
    # edited/replaced, a past reference generated from it must not vanish
    # -- only its traceability pointer clears. Nullable because a rubric-
    # only or hand-authored regeneration path may not have one.
    extracted_model_answer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_model_answers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Optional enrichment only -- populated when `ExtractedQuestion.
    # linked_question_id` happens to be set and a `Rubric` exists for that
    # `Question` (Module 04). Never required (ADR-037's "evaluation never
    # requires this to be populated" rule extends here).
    rubric_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rubrics.id", ondelete="SET NULL"), nullable=True
    )
    ai_provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ai_providers.id", ondelete="RESTRICT"), nullable=False
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", index=True)

    # --- Source content: frozen snapshots, never mutated after generation
    # (same "frozen snapshot" idiom as `AnswerEvaluation.student_answer_text`).
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    official_model_answer_text: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Structured reference content (see module docstring for why this
    # is one JSON column plus one hot-path Text column, not eight columns).
    synthesized_reference_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_content: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # --- Marking context: frozen snapshot of the max marks used, matching
    # `AnswerEvaluation.max_marks`'s own snapshot-at-use-time convention.
    maximum_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    marks_source: Mapped[str] = mapped_column(String(20), nullable=False)

    # --- AI metadata.
    provider_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    generation_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    generation_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Conflict flag: see module docstring's "CRITICAL PRINCIPLE" note.
    # `conflict_notes` is the AI's OWN self-reported explanation of a
    # detected conflict; `rejection_reason` is a separate field for a
    # teacher's reason when rejecting via `ReferenceAnswerService.reject()`
    # -- kept distinct since a teacher may reject a reference for reasons
    # unrelated to (or in addition to) an AI-flagged conflict.
    has_conflict_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    conflict_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<AIReferenceAnswer id={self.id} extracted_question_id={self.extracted_question_id} "
            f"version={self.version} status={self.status!r}>"
        )
