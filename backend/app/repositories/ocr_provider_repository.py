"""Persistence access for `OCRProvider` (global system catalog, ADR-028)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ocr_provider import OCRProvider
from app.repositories.global_repository import GlobalRepository


class OCRProviderRepository(GlobalRepository[OCRProvider]):
    search_fields = ("code", "name")
    sortable_fields = ("code", "name", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(OCRProvider, session)
