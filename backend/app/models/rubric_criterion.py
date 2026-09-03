"""RubricCriterion — a scoring criterion within a Rubric; supports self-referential sub-criteria."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class RubricCriterion(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A single scoring criterion belonging to a `Rubric`. `parent_criterion_id`
    is a self-referential FK (same table): NULL means this is a top-level
    criterion; set means this row is a sub-criterion of that parent — see
    `RubricCriterionService.create`, which also enforces that a sub-
    criterion's parent belongs to the same `rubric_id`. Both `rubric_id` and
    `parent_criterion_id` cascade: a criterion (and any sub-criteria nested
    under it) is meaningless once its rubric or parent criterion is gone.
    """

    __tablename__ = "rubric_criteria"

    rubric_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("rubrics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_criterion_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("rubric_criteria.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    weightage_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    max_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    teacher_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # AI-preparation placeholder (ADR-024): reserved for a future AI-assisted
    # grading feature to attach machine-generated notes; not read or written
    # by any code yet.
    ai_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Language Quality Intelligence milestone (Step 4.1): explicit,
    # auditable opt-in -- only a criterion with this flag set may have
    # LanguageEvidence contribute to its score, and only up to this
    # criterion's own `max_marks`. Defaults to False for every criterion
    # (including all pre-existing ones), matching the project's default
    # "language never affects marks unless explicitly authorized" policy.
    is_language_criterion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RubricCriterion id={self.id} name={self.name!r}>"
