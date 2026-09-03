"""Persistence access for `RandomizationStrategy`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.randomization_strategy import RandomizationStrategy
from app.repositories.tenant_repository import TenantScopedRepository


class RandomizationStrategyRepository(TenantScopedRepository[RandomizationStrategy]):
    search_fields: tuple[str, ...] = ()
    sortable_fields = ("strategy_type", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RandomizationStrategy, session)
