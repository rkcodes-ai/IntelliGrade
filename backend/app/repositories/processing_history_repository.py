"""Persistence access for `ProcessingHistory`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.processing_history import ProcessingHistory
from app.repositories.tenant_repository import TenantScopedRepository


class ProcessingHistoryRepository(TenantScopedRepository[ProcessingHistory]):
    search_fields = ("stage",)
    sortable_fields = ("created_at", "updated_at", "stage")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ProcessingHistory, session)
