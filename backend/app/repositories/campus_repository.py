"""Persistence access for `Campus`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campus import Campus
from app.repositories.tenant_repository import TenantScopedRepository


class CampusRepository(TenantScopedRepository[Campus]):
    search_fields = ("name", "code")
    sortable_fields = ("name", "code", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Campus, session)
