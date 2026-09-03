"""Persistence access for `DocumentRegion`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_region import DocumentRegion
from app.repositories.tenant_repository import TenantScopedRepository


class DocumentRegionRepository(TenantScopedRepository[DocumentRegion]):
    sortable_fields = ("reading_order", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(DocumentRegion, session)
