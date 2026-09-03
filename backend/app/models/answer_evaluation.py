"""AnswerEvaluation — current AI-evaluation state for one (student answer x
extracted question) pair (Module 06). See ADR-038/ADR-039/ADR-040.

Distinct from Module 04's `EvaluationHistory`, which is retained
unmodified and used as the append-only log of every AI-evaluation and
teacher-review *action* — this table is that action's *current result*,
updated in place as it moves through the review lifecycle. Same
current-state/history-log split as `AnswerScript.status` vs. Module 05's
`ProcessingHistory` (ADR-030).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AnswerEvaluation(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One student's AI-evaluated answer to one extracted question.

    `student_answer_text` is a **snapshot**, copied out of the student's
    `AnswerScript.structured_content` (Module 05, read-only — never
    modified) for this specific question at evaluation time, not
    re-derived on every read; boundary detection is best-effort and could
    shift if the OCR pipeline reruns, so freezing the text an evaluation
    was actually run against keeps past evaluations explainable.
    `max_marks` is likewise a snapshot (from the mark-scheme expansion at
    evaluation time), so a later mark-scheme edit never silently changes
    the meaning of an already-suggested or already-confirmed mark.

    Every component score (ADR-039's 7-signal pipeline) is its own
    column, never collapsed into one opaque number, for explainability.
    `confidence_tier`/`review_status` encode ADR-040's three-band review
    lifecycle. `extracted_model_answer_id` is nullable — a question may
    not yet have a matched, verified model answer.

    Unique on `(exam_session_id, extracted_question_id)` — one row per
    student-answer x question pair; re-evaluation updates in place.
    """

    __tablename__ = "answer_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "exam_session_id",
            "extracted_question_id",
            name="uq_answer_evaluation_session_question",
        ),
    )

    exam_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("exam_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    answer_script_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("answer_scripts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extracted_question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extracted_model_answer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_model_answers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ai_provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ai_providers.id", ondelete="RESTRICT"), nullable=False
    )
    # AI Reference Answer Builder milestone: the EXACT reference version
    # this evaluation was scored against, frozen at evaluation time. `SET
    # NULL` (not CASCADE) -- if a reference is later superseded or its row
    # somehow removed, a past evaluation's scores must not vanish, only
    # this traceability pointer clears. `NULL` also means "no approved
    # reference existed yet" -- see `used_legacy_reference` below, the
    # explicit, visible marker Phase 9 requires for that fallback path.
    ai_reference_answer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_reference_answers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    student_answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    semantic_similarity_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    keyword_match_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    concept_match_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    reasoning_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    completeness_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    relevance_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    confidence_tier: Mapped[str | None] = mapped_column(String(10), nullable=True)

    max_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    suggested_marks: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    final_marks: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)

    review_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", index=True
    )
    # True whenever this evaluation was scored directly against the raw
    # `ExtractedModelAnswer.answer_text` because no APPROVED
    # `AIReferenceAnswer` existed at evaluation time (not yet generated,
    # generation failed, or still pending verification) -- Phase 9's
    # explicit, visible, deterministic fallback marker, never a silent
    # substitution. Defaults `True` for backward compatibility: every
    # pre-milestone row (and every row evaluated before a reference is
    # approved) used exactly this path.
    used_legacy_reference: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<AnswerEvaluation id={self.id} exam_session_id={self.exam_session_id} "
            f"review_status={self.review_status!r}>"
        )
