"""Persistence access for `AIProvider` (global system catalog, mirrors `OCRProviderRepository`)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_provider import AIProvider
from app.repositories.global_repository import GlobalRepository


class AIProviderRepository(GlobalRepository[AIProvider]):
    search_fields = ("code", "name")
    sortable_fields = ("code", "name", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AIProvider, session)
