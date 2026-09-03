"""Batch — an intake year-group of students under a Course, e.g. "CSE 2024 Batch" (Module 03)."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Batch(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A batch belongs to exactly one course; `name` is unique per course.
    `course_id` is a raw FK column only (no `relationship()`) — `Course` was
    built in Wave 1, see `app/models/course.py`. `start_year < end_year` is
    enforced at the service layer, not the database — see
    `app/services/batch_service.py`.
    """

    __tablename__ = "batches"
    __table_args__ = (UniqueConstraint("course_id", "name", name="uq_batch_course_name"),)

    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    end_year: Mapped[int] = mapped_column(Integer, nullable=False)
    current_semester_number: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    max_strength: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Batch id={self.id} name={self.name!r}>"
