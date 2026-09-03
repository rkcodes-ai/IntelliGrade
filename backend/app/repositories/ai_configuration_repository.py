"""Persistence access for `AIConfiguration` (mirrors `OCRConfigurationRepository`)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_configuration import AIConfiguration
from app.repositories.tenant_repository import TenantScopedRepository


class AIConfigurationRepository(TenantScopedRepository[AIConfiguration]):
    search_fields: tuple[str, ...] = ()
    sortable_fields = ("created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AIConfiguration, session)
