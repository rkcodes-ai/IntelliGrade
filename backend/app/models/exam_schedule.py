"""ExamSchedule — a room/time booking for an Exam sitting (Module 04 Assessment Domain)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ExamSchedule(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A concrete room/time booking for an `Exam`: "this exam sits in this
    room, from this timestamp to that timestamp, invigilated by this user."
    There is no database-level unique constraint — a room double-booking is
    a time-range-overlap problem, checked at the service layer
    (`app/services/exam_schedule_service.py`) via
    `ExamScheduleRepository.list_for_room_in_range`, mirroring
    `ClassScheduleService._assert_no_overlap` but using absolute
    `DateTime` ranges instead of day-of-week + `Time`.

    All three FKs are raw columns only (no `relationship()`): `exam_id`
    points at a same-wave sibling model (`app/models/exam.py`) with
    `ondelete="CASCADE"` (a schedule is meaningless without its exam);
    `room_id` points at a Wave 1 model (`app/models/room.py`) with
    `ondelete="RESTRICT"` (a room must not be deletable while still
    referenced by a schedule) and is nullable (an exam schedule may be
    created before a room is assigned); `invigilator_user_id` points at
    `app/models/user.py` with `ondelete="SET NULL"` (losing the invigilator
    account shouldn't cascade-delete the schedule itself).
    """

    __tablename__ = "exam_schedules"

    exam_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    invigilator_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ExamSchedule id={self.id} exam_id={self.exam_id}>"
