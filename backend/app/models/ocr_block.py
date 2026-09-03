"""OCRBlock — one layout block (paragraph/table/image-region) within an OCRResult (Module 05)."""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class OCRBlock(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One layout block (`block_type` — `"text"` | `"table"` | `"image"`,
    best-effort per-engine classification, see
    `app.services.ocr.base.OCRBlockResult`) within an `OCRResult`'s page,
    ordered within it by `reading_order`. `bbox_*` columns are pixel
    coordinates, top-left origin, matching every OCR engine's native
    convention (see `app.services.ocr.base.BoundingBox`).

    Entirely read-only from the API's perspective; rows are written only by
    `OCRResultService.create_with_hierarchy()`, never individually.
    """

    __tablename__ = "ocr_blocks"

    ocr_result_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ocr_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    block_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    reading_order: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_left: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_top: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_width: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_height: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OCRBlock id={self.id} ocr_result_id={self.ocr_result_id}>"
