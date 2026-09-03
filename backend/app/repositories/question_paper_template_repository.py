"""Persistence access for `QuestionPaperTemplate`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_paper_template import QuestionPaperTemplate
from app.repositories.tenant_repository import TenantScopedRepository


class QuestionPaperTemplateRepository(TenantScopedRepository[QuestionPaperTemplate]):
    search_fields = ("name",)
    sortable_fields = ("name", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(QuestionPaperTemplate, session)
