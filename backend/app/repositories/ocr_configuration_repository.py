"""Persistence access for `OCRConfiguration`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ocr_configuration import OCRConfiguration
from app.repositories.tenant_repository import TenantScopedRepository


class OCRConfigurationRepository(TenantScopedRepository[OCRConfiguration]):
    search_fields: tuple[str, ...] = ()
    sortable_fields = ("created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(OCRConfiguration, session)
