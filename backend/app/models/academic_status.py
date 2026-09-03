"""AcademicStatus — lookup for a student's academic standing (Module 03 Academic Domain)."""

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AcademicStatus(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    An academic status (e.g. ACTIVE, SUSPENDED, GRADUATED, DROPPED_OUT,
    ON_LEAVE, TRANSFERRED) belongs to exactly one institution; code is
    unique per institution. `is_terminal` marks a status a student cannot
    transition out of (e.g. GRADUATED, DROPPED_OUT) — referenced by
    `StudentEnrollment`, built by a different agent in this module.
    """

    __tablename__ = "academic_statuses"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_academic_status_institution_code"),
    )

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AcademicStatus id={self.id} code={self.code!r}>"
