"""Persistence access for `AssessmentConfiguration`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment_configuration import AssessmentConfiguration
from app.repositories.tenant_repository import TenantScopedRepository


class AssessmentConfigurationRepository(TenantScopedRepository[AssessmentConfiguration]):
    search_fields: tuple[str, ...] = ()
    sortable_fields = ("created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AssessmentConfiguration, session)
