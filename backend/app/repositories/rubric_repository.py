"""Persistence access for `Rubric`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rubric import Rubric
from app.repositories.tenant_repository import TenantScopedRepository


class RubricRepository(TenantScopedRepository[Rubric]):
    search_fields = ("name",)
    sortable_fields = ("name", "total_marks", "current_version", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Rubric, session)
