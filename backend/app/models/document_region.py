"""DocumentRegion — one detected layout region on a page (Document
Intelligence milestone). Genuinely new table (not a retrofit of
`OCRBlock`, which only ever exists as the *output* of a completed OCR run
tied to one `OCRResult` — regions here are detected *before*/independently
of OCR, and drive routing decisions OCR itself doesn't make)."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class DocumentRegion(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One detected region on a page belonging to EITHER an `AnswerScriptPage`
    (Module 05) OR an `OfficialExamDocumentPage` (Module 06) — exactly one
    of `answer_script_page_id`/`official_exam_document_page_id` is set,
    enforced by `ck_document_region_exactly_one_parent`. Two nullable FKs
    rather than a generic polymorphic owner_type/owner_id pair, matching
    this codebase's existing convention of explicit per-module FKs over
    cross-module polymorphic association (see `OfficialExamDocumentPage`'s
    own docstring on why it's a parallel table rather than a shared one).

    `region_type` is this project's unified vocabulary (see
    `app.services.document_intelligence.layout.REGION_TYPES`), not any one
    detector's native label — `source_label` preserves the detector's own
    original label for audit. `extra_metadata` carries region-type-specific
    structured data (e.g. `TableStructure`'s cells for a TABLE region) as
    one JSON blob, the same "one JSON column, not eight" convention already
    used by `OCRProviderCandidate.structured_content`/`AnswerScript
    .structured_content`.
    """

    __tablename__ = "document_regions"
    __table_args__ = (
        CheckConstraint(
            "(answer_script_page_id IS NOT NULL) != (official_exam_document_page_id IS NOT NULL)",
            name="ck_document_region_exactly_one_parent",
        ),
    )

    answer_script_page_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("answer_script_pages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    official_exam_document_page_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("official_exam_document_pages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    parent_region_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_regions.id", ondelete="SET NULL"), nullable=True
    )

    region_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_label: Mapped[str] = mapped_column(String(50), nullable=False)
    source_detector: Mapped[str] = mapped_column(String(30), nullable=False)
    reading_order: Mapped[int] = mapped_column(Integer, nullable=False)

    bbox_left: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_top: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_width: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_height: Mapped[int] = mapped_column(Integer, nullable=False)

    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    classification_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    crop_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DocumentRegion id={self.id} region_type={self.region_type!r}>"
