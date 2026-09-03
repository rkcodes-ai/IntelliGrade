"""StudentEnrollment — a student enrolled into a Batch+Section for a given term (Module 03)."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class StudentEnrollment(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A student's enrollment into a batch+section, for a specific course,
    academic year and semester, tracked against an academic status. A
    student enrolls once per (academic year, semester) — see
    `uq_enrollment_student_year_semester` — and a roll number is unique
    within its section — see `uq_enrollment_section_roll_number`. Section
    capacity is enforced at the service layer against `Section.max_capacity`
    (see `app/services/student_enrollment_service.py`), not the database.

    All FKs are raw columns only (no `relationship()`): `batch_id`/
    `section_id` point at a sibling wave's models (`app/models/batch.py`,
    `app/models/section.py`); `course_id`/`academic_year_id`/
    `academic_status_id` point at Wave 1 models; `semester_id` points at a
    sibling wave's model (`app/models/semester.py`); `student_user_id`
    points at Module 02's frozen `users` table with `ondelete="RESTRICT"` —
    a user record must not be deletable while still referenced by an
    enrollment.
    """

    __tablename__ = "student_enrollments"
    __table_args__ = (
        UniqueConstraint(
            "student_user_id",
            "academic_year_id",
            "semester_id",
            name="uq_enrollment_student_year_semester",
        ),
        UniqueConstraint("section_id", "roll_number", name="uq_enrollment_section_roll_number"),
    )

    student_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    semester_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("semesters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    academic_status_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academic_statuses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    roll_number: Mapped[str] = mapped_column(String(32), nullable=False)
    enrollment_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StudentEnrollment id={self.id} roll_number={self.roll_number!r}>"
