"""Course — a specialization/branch offered under a Program (Module 03 Academic Domain)."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Course(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A course (specialization/branch) belongs to exactly one program; code is
    unique per program. `program_id` is a raw FK column only (no
    `relationship()`) — `Program` is owned by a sibling agent's model file,
    see `app/models/program.py`.
    """

    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("program_id", "code", name="uq_course_program_code"),)

    program_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_semesters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Course id={self.id} code={self.code!r}>"
