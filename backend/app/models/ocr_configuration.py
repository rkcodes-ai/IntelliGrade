"""OCRConfiguration — per-assessment (or institution-wide default) OCR settings.

Module 05 Answer Script OCR Pipeline.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class OCRConfiguration(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    OCR engine/settings selection, either scoped to one `Assessment` or, when
    `assessment_id` is `NULL`, an institution-wide default.

    `ocr_provider_id` is a raw FK column only (no `relationship()`), pointing
    at the global `OCRProvider` catalog with `ondelete="RESTRICT"` — a
    provider still referenced by a configuration must not be deletable out
    from under it. `assessment_id` uses `ondelete="CASCADE"` (a
    configuration scoped to a deleted assessment is meaningless) and is
    nullable by design. No unique constraint on `(institution_id,
    assessment_id)` — multiple institution-wide defaults would collide, but
    a nullable FK makes a clean partial-unique-index awkward and multiple
    per-institution rows are legitimate as long as `assessment_id` differs,
    so this is enforced (if at all) at the service layer, not the database
    — see `OCRConfigurationService.create`.
    """

    __tablename__ = "ocr_configurations"

    assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    ocr_provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ocr_providers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="eng")
    confidence_threshold: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    preprocessing_steps: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    max_retry_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # --- Ensemble Mode (Six-Provider OCR milestone): opt-in, off by
    # default (`is_ensemble_enabled=False`) so every existing institution's
    # behavior is completely unchanged unless explicitly turned on.
    # `ocr_provider_id` above stays the *default single-provider* choice
    # (still used verbatim whenever ensemble mode is off, or as the
    # ensemble's tie-break/highest-weighted fallback); `ensemble_provider_codes`
    # is `NULL` = "every registered, enabled local provider", or an explicit
    # subset (e.g. `["tesseract", "easyocr"]`) to control cost/latency.
    is_ensemble_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ensemble_provider_codes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OCRConfiguration id={self.id} ocr_provider_id={self.ocr_provider_id}>"
