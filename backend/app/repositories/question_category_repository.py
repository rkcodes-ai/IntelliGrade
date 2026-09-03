"""Persistence access for `QuestionCategory`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_category import QuestionCategory
from app.repositories.tenant_repository import TenantScopedRepository


class QuestionCategoryRepository(TenantScopedRepository[QuestionCategory]):
    search_fields = ("name", "code")
    sortable_fields = ("name", "code", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(QuestionCategory, session)
