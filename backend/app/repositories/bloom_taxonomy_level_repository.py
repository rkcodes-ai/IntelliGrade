"""Persistence access for `BloomTaxonomyLevel`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bloom_taxonomy_level import BloomTaxonomyLevel
from app.repositories.tenant_repository import TenantScopedRepository


class BloomTaxonomyLevelRepository(TenantScopedRepository[BloomTaxonomyLevel]):
    search_fields = ("name", "code")
    sortable_fields = ("name", "code", "level_order", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(BloomTaxonomyLevel, session)
