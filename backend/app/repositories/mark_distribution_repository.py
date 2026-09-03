"""Persistence access for `MarkDistribution`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mark_distribution import MarkDistribution
from app.repositories.tenant_repository import TenantScopedRepository


class MarkDistributionRepository(TenantScopedRepository[MarkDistribution]):
    search_fields = ("band_name",)
    sortable_fields = ("band_name", "min_score", "max_score", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(MarkDistribution, session)
