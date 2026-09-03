"""Persistence access for `Batch`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import Batch
from app.repositories.tenant_repository import TenantScopedRepository


class BatchRepository(TenantScopedRepository[Batch]):
    search_fields = ("name",)
    sortable_fields = ("name", "start_year", "end_year", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Batch, session)
