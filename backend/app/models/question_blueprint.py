"""QuestionBlueprint — a target question distribution for a Subject (Module 04)."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.assessment_base import VersionCounterMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class QuestionBlueprint(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    VersionCounterMixin,
    Base,
):
    """
    A named target distribution of questions (total marks/count) for a
    `Subject`; concrete category/difficulty/bloom/type breakdowns live in
    the child `QuestionBlueprintSection` rows (`app/models/
    question_blueprint_section.py`). `subject_id` points at a Module 03
    entity (`app/models/subject.py`) and uses `ondelete="CASCADE"` — a
    blueprint is meaningless without its subject, same convention as
    `Question.subject_id`. `current_version` (via `VersionCounterMixin`) is
    bumped by `QuestionBlueprintService.update` on any content-changing
    edit.
    """

    __tablename__ = "question_blueprints"

    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    total_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<QuestionBlueprint id={self.id} name={self.name!r}>"
