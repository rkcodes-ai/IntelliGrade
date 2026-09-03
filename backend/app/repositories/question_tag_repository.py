"""Persistence access for `QuestionTag`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_tag import QuestionTag
from app.repositories.tenant_repository import TenantScopedRepository


class QuestionTagRepository(TenantScopedRepository[QuestionTag]):
    search_fields = ("name",)
    sortable_fields = ("name", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(QuestionTag, session)
