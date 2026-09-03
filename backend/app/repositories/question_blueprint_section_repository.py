"""Persistence access for `QuestionBlueprintSection`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_blueprint_section import QuestionBlueprintSection
from app.repositories.tenant_repository import TenantScopedRepository


class QuestionBlueprintSectionRepository(TenantScopedRepository[QuestionBlueprintSection]):
    search_fields = ()
    sortable_fields = ("display_order", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(QuestionBlueprintSection, session)
