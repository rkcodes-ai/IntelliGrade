"""Persistence access for `Program`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.program import Program
from app.repositories.tenant_repository import TenantScopedRepository


class ProgramRepository(TenantScopedRepository[Program]):
    search_fields = ("name", "code")
    sortable_fields = ("name", "code", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Program, session)
