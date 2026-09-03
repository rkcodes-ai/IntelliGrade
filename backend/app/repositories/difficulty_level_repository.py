"""Persistence access for `DifficultyLevel`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.difficulty_level import DifficultyLevel
from app.repositories.tenant_repository import TenantScopedRepository


class DifficultyLevelRepository(TenantScopedRepository[DifficultyLevel]):
    search_fields = ("name", "code")
    sortable_fields = ("name", "code", "level_order", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(DifficultyLevel, session)
