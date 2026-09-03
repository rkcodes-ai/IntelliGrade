"""AssessmentConfiguration — 1:1 marking/attempt configuration for an Assessment.

Module 04 Assessment Domain.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Numeric, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AssessmentConfiguration(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    Marking scheme and attempt rules for exactly one `Assessment`.

    `Assessment` is a sibling table built in parallel in this same wave (see
    `app/models/assessment.py`) — `assessment_id` is a raw FK column only (no
    `relationship()`), matching every other Module 03/04 cross-table
    reference. `unique=True` enforces the 1:1 relationship at the database
    level; `ondelete="CASCADE"` because a configuration row is meaningless
    without its parent assessment.
    """

    __tablename__ = "assessment_configurations"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    maximum_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    passing_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    negative_marks: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True, default=Decimal("0")
    )
    grace_marks: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True, default=Decimal("0")
    )
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt_rules: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AssessmentConfiguration id={self.id} assessment_id={self.assessment_id}>"
