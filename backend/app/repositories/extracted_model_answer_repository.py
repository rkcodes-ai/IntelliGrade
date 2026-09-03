"""Persistence access for `ExtractedModelAnswer` (Module 06)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extracted_model_answer import ExtractedModelAnswer
from app.repositories.tenant_repository import TenantScopedRepository


class ExtractedModelAnswerRepository(TenantScopedRepository[ExtractedModelAnswer]):
    search_fields: tuple[str, ...] = ()
    sortable_fields = ("display_order", "question_number", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ExtractedModelAnswer, session)
