"""Persistence access for `OCRResult`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ocr_result import OCRResult
from app.repositories.tenant_repository import TenantScopedRepository


class OCRResultRepository(TenantScopedRepository[OCRResult]):
    search_fields = ("language",)
    sortable_fields = ("created_at", "updated_at", "average_confidence")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(OCRResult, session)
