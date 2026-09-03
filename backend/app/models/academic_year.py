"""AcademicYear — an institution-wide academic year, e.g. "2025-2026" (Module 03)."""

from datetime import date

from sqlalchemy import Boolean, Date, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AcademicYear(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    An academic year belongs to exactly one institution; `year_label` is
    unique per institution. Date-range overlap and `start_date < end_date`
    business rules are enforced at the service layer, not the database —
    see `app/services/academic_year_service.py`. `status` is a free-form
    string validated at the schema layer
    (`Literal["planned", "active", "completed", "archived"]`).
    """

    __tablename__ = "academic_years"
    __table_args__ = (
        UniqueConstraint("institution_id", "year_label", name="uq_academic_year_institution_label"),
    )

    year_label: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AcademicYear id={self.id} year_label={self.year_label!r}>"
