"""AssessmentType — lookup for the kind of an Assessment (Module 04 Assessment Domain)."""

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AssessmentType(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    An assessment type (e.g. QUIZ, MIDTERM, FINAL, ASSIGNMENT) belongs to
    exactly one institution; code is unique per institution. Referenced by
    `Assessment.assessment_type_id`.
    """

    __tablename__ = "assessment_types"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_assessment_type_institution_code"),
    )

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AssessmentType id={self.id} code={self.code!r}>"
