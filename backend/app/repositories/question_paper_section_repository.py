"""Persistence access for `QuestionPaperSection`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_paper_section import QuestionPaperSection
from app.repositories.tenant_repository import TenantScopedRepository


class QuestionPaperSectionRepository(TenantScopedRepository[QuestionPaperSection]):
    search_fields = ("name",)
    sortable_fields = ("name", "display_order", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(QuestionPaperSection, session)
