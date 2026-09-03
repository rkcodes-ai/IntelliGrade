"""OCRResult — persisted OCR output for one AnswerScriptPage (Module 05, ADR-029)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class OCRResult(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    Root of the OCR output hierarchy (`OCRResult 1-* OCRBlock 1-* OCRLine
    1-* OCRWord` — see ADR-029 for why there's no separate "paragraph"
    level) — one row per `AnswerScriptPage`, 1:1 (`answer_script_page_id`
    is unique).

    Entirely read-only from the API's perspective (`GET`-only router, see
    `app/api/v1/endpoints/ocr_results.py`); rows are written exclusively by
    `OCRResultService.create_with_hierarchy()`, called directly by
    pipeline/task code with an `app.services.ocr.base.OCRPageResult` (never
    through an HTTP route). `answer_script_page_id`/`ocr_job_id` are raw FK
    columns only (no `relationship()`) — `AnswerScriptPage`/`OCRJob` are
    sibling tables built by other engineers this same wave; string table
    names are used so this file doesn't depend on their models existing yet.
    `normalized_text` stays `NULL` at creation time — populated by a later
    Stage 7 pipeline step, not part of `create_with_hierarchy()`.
    """

    __tablename__ = "ocr_results"

    answer_script_page_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("answer_script_pages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    ocr_job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ocr_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    average_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    rotation_degrees: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    reading_order_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- Module 12: Multi-OCR Platform provider metadata (additive, all nullable
    # so every pre-Module-12 row and every provider that doesn't populate a given
    # field stays valid). `raw_response_reference` is a pointer (e.g. a storage
    # key) to the provider's raw response payload, not the payload itself --
    # keeps this row lean regardless of how large/nested a given engine's native
    # response is.
    provider_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_response_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- Ensemble Mode (Six-Provider OCR milestone): when a page was
    # processed by more than one local provider and fused, these record
    # *that this row is a fusion result* rather than a single provider's
    # direct output -- `raw_text`/`normalized_text`/`average_confidence`
    # above stay the same columns either way, so every pre-Ensemble-Mode
    # consumer of `OCRResult` is unaffected. Each contributing provider's
    # own raw candidate is preserved separately in `OCRProviderCandidate`
    # rows (never discarded), linked via `ocr_result_id`.
    is_ensemble_result: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    contributing_provider_codes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    disagreement_regions: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)

    # --- Language Quality Intelligence milestone (Step 4.1): serialized
    # `LanguageEvidence.to_dict()` for this page's fused text, same "one
    # JSON blob" convention as `disagreement_regions` above. `None` means
    # language analysis hasn't run (or is disabled) for this row -- never
    # a signal of "language is perfect".
    language_quality_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )

    # --- Indian Multilingual Document Intelligence milestone (Step 4.2):
    # serialized script detection + fastText language identification +
    # resolved LanguageContext + OCR-routing provenance, same "one JSON
    # blob" convention as `disagreement_regions`/`language_quality_metadata`
    # above. `language` (pre-existing column) is now actually populated
    # from the resolved context instead of always being the hardcoded
    # "eng" literal it was before this milestone.
    multilingual_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # Reviewer override (Section 38) -- all nullable; most rows never
    # have one, which is the correct default state, not an error.
    language_reviewer_verified_language: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    language_reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    language_reviewer_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OCRResult id={self.id} answer_script_page_id={self.answer_script_page_id}>"
