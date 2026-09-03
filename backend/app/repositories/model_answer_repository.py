"""Persistence access for `ModelAnswer`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_answer import ModelAnswer
from app.repositories.tenant_repository import TenantScopedRepository


class ModelAnswerRepository(TenantScopedRepository[ModelAnswer]):
    search_fields: tuple[str, ...] = ("content",)
    sortable_fields = ("display_order", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ModelAnswer, session)
