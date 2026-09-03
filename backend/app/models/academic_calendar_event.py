"""AcademicCalendarEvent — holidays, exam periods, registration windows (Module 03)."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AcademicCalendarEvent(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A dated event (holiday, exam period, registration window, orientation,
    or other) within an `AcademicYear`. `academic_year_id` is a raw FK
    column only (no `relationship()`) — `AcademicYear` was built in Wave 1,
    see `app/models/academic_year.py`. No uniqueness constraint: multiple
    events may legitimately share dates or titles. `event_type` is a
    free-form string validated at the schema layer
    (`Literal["holiday", "exam", "registration", "orientation", "other"]`),
    not constrained in the database. `start_date <= end_date` is enforced at
    the service layer — see `app/services/academic_calendar_event_service.py`.
    """

    __tablename__ = "academic_calendar_events"

    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_holiday: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AcademicCalendarEvent id={self.id} title={self.title!r}>"
