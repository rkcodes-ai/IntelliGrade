"""Persistence access for `Assessment`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.repositories.tenant_repository import TenantScopedRepository


class AssessmentRepository(TenantScopedRepository[Assessment]):
    search_fields = ("name",)
    sortable_fields = ("name", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Assessment, session)
