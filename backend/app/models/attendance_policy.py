"""AttendancePolicy — institution-wide or program-specific attendance rules.

Module 03 Academic Domain.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AttendancePolicy(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    An attendance policy belongs to exactly one institution; name is unique
    per institution. `program_id` is a plain, unvalidated nullable FK to
    `programs.id` — same simplification as `GradingPolicy.program_id` (see
    that model's docstring). Foundation only: no session-level attendance
    tracking table exists yet — that's a future module.
    """

    __tablename__ = "attendance_policies"
    __table_args__ = (
        UniqueConstraint("institution_id", "name", name="uq_attendance_policy_institution_name"),
    )

    program_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("programs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    minimum_attendance_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    condonation_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AttendancePolicy id={self.id} name={self.name!r}>"
