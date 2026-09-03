"""Persistence access for `EvaluationHistory`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation_history import EvaluationHistory
from app.repositories.tenant_repository import TenantScopedRepository


class EvaluationHistoryRepository(TenantScopedRepository[EvaluationHistory]):
    search_fields: tuple[str, ...] = ()
    sortable_fields = ("evaluated_at", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(EvaluationHistory, session)
