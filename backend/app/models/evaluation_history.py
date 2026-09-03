"""EvaluationHistory — append-only log of evaluation attempts against an ExamSession (ADR-024)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class EvaluationHistory(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One append-only record of an evaluation attempt against an
    `ExamSession` — who (or what) evaluated it, what score resulted, and
    (per ADR-024) placeholder fields reserved for a future automated/AI
    evaluation pipeline that does not exist yet in this codebase.

    This entity is create/read-only in practice: there is no
    `EVALUATION_HISTORY_UPDATE`/`DELETE` permission code, so
    `app/api/v1/endpoints/evaluation_history.py` exposes only
    `GET ""`, `GET "/{id}"`, `POST ""`. The model/repository/service still
    provide the standard soft-delete-capable surface for consistency with
    every other Assessment Domain entity's base classes, even though no
    route reaches it.

    `exam_session_id` and `answer_key_id` are raw columns only (no
    `relationship()`), pointing at sibling-wave models
    (`app/models/exam_session.py`, `app/models/answer_key.py`) owned by
    other agents in this same wave. `exam_session_id` cascades (a history
    row is meaningless without the exam session it evaluates);
    `answer_key_id` is `ondelete="SET NULL"` (an answer key can be
    retired/replaced without destroying the historical evaluation record
    that used it). `evaluator_user_id` points at the real, already-merged
    `User` (Module 02), also `ondelete="SET NULL"` for the same reason.
    """

    __tablename__ = "evaluation_history"

    exam_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("exam_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    answer_key_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("answer_keys.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    evaluator_type: Mapped[str] = mapped_column(String(10), nullable=False, default="human")
    evaluator_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    # AI-preparation placeholder per ADR-024: a future automated-evaluation
    # confidence value (0-1); not read or written by any code yet.
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    # AI-preparation placeholder per ADR-024: a plain float-array stand-in
    # for a future embedding vector (NOT pgvector); not used by any code yet.
    embedding_vector: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EvaluationHistory id={self.id} evaluator_type={self.evaluator_type!r}>"
