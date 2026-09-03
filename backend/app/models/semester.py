"""Semester — a term within an AcademicYear, e.g. "Semester 1" (Module 03 Academic Domain)."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Semester(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A semester belongs to exactly one academic year; `semester_number` is
    unique per academic year. `academic_year_id` is a raw FK column only (no
    `relationship()`) — `AcademicYear` was built in Wave 1, see
    `app/models/academic_year.py`. Date-range-within-parent, sibling-overlap
    and `start_date < end_date` business rules are enforced at the service
    layer, not the database — see `app/services/semester_service.py`.
    `term_type`/`status` are free-form strings validated at the schema layer.
    """

    __tablename__ = "semesters"
    __table_args__ = (
        UniqueConstraint(
            "academic_year_id", "semester_number", name="uq_semester_academic_year_number"
        ),
    )

    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    semester_number: Mapped[int] = mapped_column(Integer, nullable=False)
    term_type: Mapped[str] = mapped_column(String(10), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Semester id={self.id} name={self.name!r}>"
