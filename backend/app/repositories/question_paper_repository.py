"""Persistence access for `QuestionPaper`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_paper import QuestionPaper
from app.repositories.tenant_repository import TenantScopedRepository


class QuestionPaperRepository(TenantScopedRepository[QuestionPaper]):
    search_fields = ("name",)
    sortable_fields = ("name", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(QuestionPaper, session)
