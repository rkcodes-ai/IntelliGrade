"""Persistence access for `EvaluationConfiguration`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation_configuration import EvaluationConfiguration
from app.repositories.tenant_repository import TenantScopedRepository


class EvaluationConfigurationRepository(TenantScopedRepository[EvaluationConfiguration]):
    search_fields: tuple[str, ...] = ()
    sortable_fields = ("created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(EvaluationConfiguration, session)
