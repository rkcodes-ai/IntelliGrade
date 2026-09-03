"""OCRProviderCandidate — one OCR provider's raw candidate output for one
page, captured during Ensemble Mode (Six-Provider OCR milestone, Phase
"OCR Ensemble & Fusion").

**Why this exists.** `OCRResult` (ADR-029) is one row per page holding
*the* text IntelliGrade uses downstream — historically always from a
single resolved provider. Ensemble Mode runs several local providers
against the same page and fuses their output into that same `OCRResult`
row (so every existing consumer of `OCRResult`/`OCRBlock`/`OCRLine`/
`OCRWord` is completely unaffected). This table is the **additive**
record of what each individual provider actually produced before fusion
— never discarded, per the milestone's "preserve raw OCR results"
requirement, and essential for auditing *why* the fusion engine chose
what it chose.

One JSON column (`structured_content`), not a parallel
Candidate→Block→Line→Word relational tree — same "one JSON column, not
eight" reasoning as `AnswerScript.structured_content` (ADR-031) and
`AIReferenceAnswer.structured_content`: a candidate's block/line/word
tree is read as one unit (by the fusion engine, and by any future
"inspect what provider X actually saw" debugging UI), never queried
column-by-column, so a nested JSON blob is the right shape, not a second
copy of ADR-029's relational hierarchy per provider.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class OCRProviderCandidate(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    __tablename__ = "ocr_provider_candidates"
    __table_args__ = (
        UniqueConstraint(
            "ocr_result_id", "provider_code", name="uq_ocr_provider_candidate_result_provider"
        ),
    )

    ocr_result_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ocr_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "success" | "failed"
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    # Full block->line->word tree for this candidate, same shape as
    # `app.services.ocr.base.OCRPageResult` serialized to JSON -- read as
    # one unit by the fusion engine, never queried piecemeal.
    structured_content: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<OCRProviderCandidate id={self.id} ocr_result_id={self.ocr_result_id} "
            f"provider_code={self.provider_code!r} status={self.status!r}>"
        )
