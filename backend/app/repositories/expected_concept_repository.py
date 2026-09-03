"""Persistence access for `ExpectedConcept`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expected_concept import ExpectedConcept
from app.repositories.tenant_repository import TenantScopedRepository


class ExpectedConceptRepository(TenantScopedRepository[ExpectedConcept]):
    search_fields = ("concept_name",)
    sortable_fields = ("concept_name", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ExpectedConcept, session)
