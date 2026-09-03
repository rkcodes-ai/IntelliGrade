"""OCRWord — one recognized word within an OCRLine (Module 05)."""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class OCRWord(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One recognized word within an `OCRLine`, the leaf of the OCR output
    hierarchy (`OCRResult 1-* OCRBlock 1-* OCRLine 1-* OCRWord` — see
    ADR-029), ordered within its line by `reading_order`. `bbox_*` columns
    are pixel coordinates, top-left origin, matching every OCR engine's
    native convention (see `app.services.ocr.base.BoundingBox`).

    Entirely read-only from the API's perspective; rows are written only by
    `OCRResultService.create_with_hierarchy()`, never individually.
    """

    __tablename__ = "ocr_words"

    ocr_line_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ocr_lines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(String(255), nullable=False)
    reading_order: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_left: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_top: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_width: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_height: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OCRWord id={self.id} ocr_line_id={self.ocr_line_id}>"
