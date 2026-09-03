"""Rubric — a grading rubric, optionally tied to a Question, or a reusable template (Module 04)."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.assessment_base import VersionCounterMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Rubric(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    VersionCounterMixin,
    Base,
):
    """
    A grading rubric: either bound to one specific `Question` (`question_id`
    set) or a reusable template not yet attached to any question
    (`question_id` NULL) — see `RubricService.create`. `question_id`
    cascades: a rubric permanently tied to a question is meaningless once
    that question is gone, but a template rubric (`question_id IS NULL`) is
    entirely unaffected by any question's lifecycle.
    """

    __tablename__ = "rubrics"

    question_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    total_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Rubric id={self.id} name={self.name!r}>"
