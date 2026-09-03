"""Question — a single assessment question in the institution's question bank (Module 04)."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.assessment_base import ApprovalWorkflowMixin, VersionCounterMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Question(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    VersionCounterMixin,
    ApprovalWorkflowMixin,
    Base,
):
    """
    A single question in the institution's question bank.

    There is intentionally no separate `status` column: `approval_status`
    (from `ApprovalWorkflowMixin`) already models this entity's full
    lifecycle (draft -> pending_review -> approved/rejected -> archived) —
    see `app/services/question_service.py` for the state-transition rules.

    All five parent FKs are raw columns only (no `relationship()`).
    `subject_id` points at a Module 03 entity (`app/models/subject.py`) and
    cascades — a question is meaningless without its subject.
    `question_category_id`/`question_type_id`/`difficulty_level_id`/
    `bloom_level_id` point at sibling Module 04 lookup tables built in the
    same wave (`question_categories`, `question_types`, `difficulty_levels`,
    `bloom_taxonomy_levels`) and use `ondelete="RESTRICT"` — a lookup value
    still referenced by a question must not be deletable out from under it.

    `question_metadata` (not `metadata`, which `DeclarativeBase` reserves)
    is a free-form JSON bag for anything not worth its own column.
    """

    __tablename__ = "questions"

    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    question_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    difficulty_level_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("difficulty_levels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    bloom_level_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bloom_taxonomy_levels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    unit: Mapped[str | None] = mapped_column(String(200), nullable=True)
    chapter: Mapped[str | None] = mapped_column(String(200), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    subtopic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    learning_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    attachments: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    diagram_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    question_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Question id={self.id} approval_status={self.approval_status!r}>"
