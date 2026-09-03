"""Persistence access for `QuestionBlueprint`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_blueprint import QuestionBlueprint
from app.repositories.tenant_repository import TenantScopedRepository


class QuestionBlueprintRepository(TenantScopedRepository[QuestionBlueprint]):
    search_fields = ("name",)
    sortable_fields = ("name", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(QuestionBlueprint, session)
