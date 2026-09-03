"""AnswerKey — the single authoritative answer key for a Question, 1:1 (Module 04)."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, Numeric, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.assessment_base import VersionCounterMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AnswerKey(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    VersionCounterMixin,
    Base,
):
    """
    The single authoritative answer key for a `Question` — a strict 1:1
    relationship enforced by `unique=True` on `question_id`. The service
    layer (`AnswerKeyService.create`) also pre-checks this before insert so
    callers get a clean 409 instead of a raw integrity error — same pattern
    as `AssessmentConfiguration.assessment_id`
    (`app/models/assessment_configuration.py`).

    `question_id` is a raw column only (no `relationship()`) and uses
    `ondelete="CASCADE"`: an answer key is meaningless once its question is
    gone.

    `confidence_threshold` and `ai_config` are AI-preparation placeholders
    per ADR-024 — no code reads or writes them yet; they exist only so a
    future AI-assisted evaluation feature doesn't require a migration.
    """

    __tablename__ = "answer_keys"

    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    reference_answer: Mapped[str] = mapped_column(Text, nullable=False)
    expected_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_structure: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # AI-preparation placeholder per ADR-024 — not read or written by any code yet.
    confidence_threshold: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    # AI-preparation placeholder per ADR-024 — not read or written by any code yet.
    ai_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    evaluation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AnswerKey id={self.id} question_id={self.question_id}>"
