"""QuestionType — the answer format a Question takes (MCQ, essay, etc.).

Module 04 Assessment Domain.
"""

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class QuestionType(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """A question type belongs to exactly one institution; code is unique per institution."""

    __tablename__ = "question_types"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_question_type_institution_code"),
    )

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Hints whether the UI should show an options editor (e.g. true for
    #: MCQ/Matching/True-False, false for Essay/Short-Answer).
    requires_options: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<QuestionType id={self.id} code={self.code!r}>"
