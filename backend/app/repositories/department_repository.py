"""Persistence access for `Department`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department
from app.repositories.tenant_repository import TenantScopedRepository


class DepartmentRepository(TenantScopedRepository[Department]):
    search_fields = ("name", "code")
    sortable_fields = ("name", "code", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Department, session)
