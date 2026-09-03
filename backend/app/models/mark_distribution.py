"""MarkDistribution — a scoring band (e.g. "Excellent"/"Good") for a RubricCriterion (Module 04)."""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class MarkDistribution(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One scoring band within a `RubricCriterion`'s mark range (e.g.
    "Excellent" = 8-10, "Good" = 5-7, "Average" = 3-4, "Poor" = 0-2).
    `rubric_criterion_id` cascades: a band is meaningless once its criterion
    is gone. `min_score <= max_score` is enforced at the service layer
    (`MarkDistributionService.create`/`update`), not the database.
    """

    __tablename__ = "mark_distributions"

    rubric_criterion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("rubric_criteria.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    band_name: Mapped[str] = mapped_column(String(100), nullable=False)
    min_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    max_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MarkDistribution id={self.id} band_name={self.band_name!r}>"
