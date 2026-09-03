"""ClassSchedule — a recurring weekly timetable slot binding a SubjectAllocation to a Room."""

import uuid
from datetime import time

from sqlalchemy import Boolean, ForeignKey, String, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ClassSchedule(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A recurring weekly timetable slot: "this subject allocation meets in
    this room on this day of the week, from this time to that time." There
    is no database-level unique constraint — a room double-booking is a
    time-range-overlap problem, checked at the service layer
    (`app/services/class_schedule_service.py`) via
    `ClassScheduleRepository.list_for_room_and_day`.

    Both FKs are raw columns only (no `relationship()`):
    `subject_allocation_id` points at a sibling wave's model
    (`app/models/subject_allocation.py`); `room_id` points at a Wave 1 model
    (`app/models/room.py`) with `ondelete="RESTRICT"` — a room must not be
    deletable while still referenced by a schedule.
    """

    __tablename__ = "class_schedules"

    subject_allocation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subject_allocations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    day_of_week: Mapped[str] = mapped_column(String(10), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ClassSchedule id={self.id} day_of_week={self.day_of_week!r}>"
