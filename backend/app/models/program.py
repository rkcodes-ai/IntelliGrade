"""Program — belongs to a Department (Module 03 Academic Domain)."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Program(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A program (degree) belongs to exactly one department; code is unique per
    department. `degree_type` is a free-form string validated at the schema
    layer (`Literal["ug", "pg", "diploma", "doctorate", "certificate"]`), not
    constrained in the database — see `app/schemas/program.py`.
    """

    __tablename__ = "programs"
    __table_args__ = (UniqueConstraint("department_id", "code", name="uq_program_department_code"),)

    department_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    degree_type: Mapped[str] = mapped_column(String(32), nullable=False)
    duration_years: Mapped[int] = mapped_column(Integer, nullable=False)
    total_semesters: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Program id={self.id} code={self.code!r}>"
