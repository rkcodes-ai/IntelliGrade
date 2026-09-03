"""OCRProvider — global OCR engine catalog (Module 05 Answer Script OCR Pipeline).

See ADR-028 in `ARCHITECTURE_DECISIONS.md`: an OCR engine catalog (tesseract,
easyocr, paddleocr, azure_ocr, google_vision, aws_textract) is system/
technical data, identical across every institution, not per-tenant content —
so this is the one entity in this module that does NOT compose
`InstitutionOwnedMixin`.
"""

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class OCRProvider(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    Catalog entry for one OCR engine (e.g. `"tesseract"`, `"azure_ocr"`).

    Rows are seeded by migration, not created via the API — the router only
    exposes `GET`/`PATCH` (see `app/api/v1/endpoints/ocr_providers.py`).
    `code`/`name`/`is_implemented` are immutable after seeding; only
    `is_enabled`/`is_default` are patchable, both enforced by
    `OCRProviderService.update`: at most one row may have `is_default=True`
    at a time, and `is_enabled=True` requires `is_implemented=True` (a
    catalog entry may exist for an engine whose adapter isn't written yet —
    see `OCRProviderNotImplementedError`, ADR-032).
    """

    __tablename__ = "ocr_providers"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_implemented: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OCRProvider id={self.id} code={self.code!r}>"
