"""AssessmentStatus — lookup for the lifecycle state of an Assessment (Module 04)."""

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AssessmentStatus(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    An assessment status (e.g. DRAFT, SCHEDULED, IN_PROGRESS, COMPLETED,
    CANCELLED) belongs to exactly one institution; code is unique per
    institution. `is_terminal` marks a status an assessment cannot
    transition out of (e.g. COMPLETED, CANCELLED) — mirrors
    `app/models/academic_status.py` from Module 03. Referenced by
    `Assessment.assessment_status_id`.
    """

    __tablename__ = "assessment_statuses"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_assessment_status_institution_code"),
    )

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AssessmentStatus id={self.id} code={self.code!r}>"
