"""Persistence access for `QuestionType`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_type import QuestionType
from app.repositories.tenant_repository import TenantScopedRepository


class QuestionTypeRepository(TenantScopedRepository[QuestionType]):
    search_fields = ("name", "code")
    sortable_fields = ("name", "code", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(QuestionType, session)
