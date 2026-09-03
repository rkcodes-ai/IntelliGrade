"""SubjectAllocation — binds a Subject to a Section for a Semester+AcademicYear (Module 03)."""

import uuid

from sqlalchemy import Boolean, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class SubjectAllocation(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    "This subject is taught in this section this semester, by this
    teacher, optionally in this room." A given (subject, section, semester)
    triple may only be allocated once — see `uq_subject_allocation_subject_section_semester`.

    All FKs are raw columns only (no `relationship()`): `subject_id` points
    at a sibling model in this same task (`app/models/subject.py`);
    `section_id`/`semester_id` point at models owned by a parallel sibling
    agent in this same wave (`app/models/section.py`, `app/models/semester.py`);
    `academic_year_id`/`room_id` point at Wave 1 models
    (`app/models/academic_year.py`, `app/models/room.py`); `teacher_user_id`
    points at Module 02's frozen `users` table. `room_id` is nullable with
    `ondelete="SET NULL"` — losing a room shouldn't destroy the allocation,
    only clear its room assignment. `teacher_user_id` uses
    `ondelete="RESTRICT"` — a user record must not be deletable while still
    referenced as a teacher of record.
    """

    __tablename__ = "subject_allocations"
    __table_args__ = (
        UniqueConstraint(
            "subject_id",
            "section_id",
            "semester_id",
            name="uq_subject_allocation_subject_section_semester",
        ),
    )

    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    semester_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("semesters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    teacher_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    room_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SubjectAllocation id={self.id} subject_id={self.subject_id}>"
