"""AIConfiguration — per-assessment (or institution-wide default) AI
evaluation provider selection (Module 06). Mirrors
`app.models.ocr_configuration.OCRConfiguration`'s shape."""

import uuid
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AIConfiguration(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    AI evaluation provider selection, either scoped to one `Assessment` or,
    when `assessment_id` is `NULL`, an institution-wide default — identical
    shape to `OCRConfiguration`. Confidence-tier thresholds (ADR-040) are
    deliberately **not** a column here in this pass — they're named
    constants in `AnswerEvaluationService`, not a per-institution override
    (see ADR-040/ADR-041 for why). `provider_config` is a generic JSON
    passthrough for future provider-specific tuning, matching the
    `ai_config` JSON precedent already established on `AnswerKey`/
    `EvaluationConfiguration` (Module 04, ADR-024).
    """

    __tablename__ = "ai_configurations"

    assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    ai_provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_providers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    provider_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AIConfiguration id={self.id} ai_provider_id={self.ai_provider_id}>"
