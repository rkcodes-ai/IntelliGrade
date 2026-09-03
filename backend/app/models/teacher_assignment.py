"""TeacherAssignment — a teacher assigned to a SubjectAllocation (Module 03 Academic Domain)."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class TeacherAssignment(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    Binds a teacher (`users.id`) to a `SubjectAllocation`, supporting more
    than one teacher per allocation (e.g. primary + assistant). At most one
    active "primary" assignment is allowed per allocation — enforced at the
    service layer (`app/services/teacher_assignment_service.py`), not the
    database, since it's a conditional (role == "primary") uniqueness rule.
    `subject_allocation_id` is a raw FK column only (no `relationship()`) —
    `SubjectAllocation` is owned by a sibling agent's model file, see
    `app/models/subject_allocation.py`. `teacher_user_id` points at Module
    02's frozen `users` table with `ondelete="RESTRICT"` — a user record
    must not be deletable while still referenced as an assigned teacher.
    """

    __tablename__ = "teacher_assignments"
    __table_args__ = (
        UniqueConstraint(
            "subject_allocation_id",
            "teacher_user_id",
            name="uq_teacher_assignment_allocation_teacher",
        ),
    )

    teacher_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subject_allocation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subject_allocations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assignment_role: Mapped[str] = mapped_column(String(20), nullable=False, default="primary")
    assigned_from: Mapped[date] = mapped_column(Date, nullable=False)
    assigned_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TeacherAssignment id={self.id} role={self.assignment_role!r}>"
