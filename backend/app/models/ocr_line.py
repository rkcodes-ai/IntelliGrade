"""OCRLine — one text line within an OCRBlock (Module 05)."""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class OCRLine(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One text line within an `OCRBlock`, ordered within it by
    `reading_order`. `bbox_*` columns are pixel coordinates, top-left
    origin, matching every OCR engine's native convention (see
    `app.services.ocr.base.BoundingBox`).

    Entirely read-only from the API's perspective; rows are written only by
    `OCRResultService.create_with_hierarchy()`, never individually.
    """

    __tablename__ = "ocr_lines"

    ocr_block_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ocr_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    reading_order: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_left: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_top: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_width: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_height: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OCRLine id={self.id} ocr_block_id={self.ocr_block_id}>"
