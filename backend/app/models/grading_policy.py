"""GradingPolicy — institution-wide or program-specific grading rules.

Module 03 Academic Domain.
"""

import uuid
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class GradingPolicy(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A grading policy belongs to exactly one institution; name is unique per
    institution. `program_id` is a plain, unvalidated nullable FK to
    `programs.id`: null means institution-wide, set means program-specific.
    `Program` is being built by a different, parallel agent in this module
    — deliberately not validated or joined via `relationship()` here (a
    documented simplification; see `ARCHITECTURE_DECISIONS.md` and the
    Module 03 style guide). A follow-up module can add the FK-existence
    check once all Academic Domain entities have landed.
    """

    __tablename__ = "grading_policies"
    __table_args__ = (
        UniqueConstraint("institution_id", "name", name="uq_grading_policy_institution_name"),
    )

    program_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("programs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    grading_scale: Mapped[str] = mapped_column(String(20), nullable=False)
    passing_criteria: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    grade_bands: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<GradingPolicy id={self.id} name={self.name!r}>"
