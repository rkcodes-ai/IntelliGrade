"""EvaluationConfiguration — 1:1 evaluation-mode configuration for an Assessment.

Module 04 Assessment Domain.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class EvaluationConfiguration(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    Evaluation-mode configuration for exactly one `Assessment`.

    `Assessment` is a sibling table built in parallel in this same wave (see
    `app/models/assessment.py`) — `assessment_id` is a raw FK column only (no
    `relationship()`). `unique=True` enforces the 1:1 relationship at the
    database level; `ondelete="CASCADE"` because a configuration row is
    meaningless without its parent assessment. `evaluation_mode` is a plain
    string, `Literal["manual", "auto", "hybrid"]`-typed at the Pydantic
    schema level (no DB CHECK constraint) — same idiom as Module 03's
    `AcademicYear.status`.

    `confidence_threshold` and `ai_config` are Module 05/06 AI-preparation
    placeholders per ADR-024 — not used by any code in this module, just
    stored for a future automated-evaluation feature to read.
    """

    __tablename__ = "evaluation_configurations"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    evaluation_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    # AI-preparation placeholder (ADR-024): future confidence cutoff for
    # auto-evaluation; not read or written by any code in this module yet.
    confidence_threshold: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    # AI-preparation placeholder (ADR-024): future model/provider config;
    # not read or written by any code in this module yet.
    ai_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    auto_publish_results: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EvaluationConfiguration id={self.id} assessment_id={self.assessment_id}>"
