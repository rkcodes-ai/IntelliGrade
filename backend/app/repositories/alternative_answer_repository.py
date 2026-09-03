"""Persistence access for `AlternativeAnswer`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alternative_answer import AlternativeAnswer
from app.repositories.tenant_repository import TenantScopedRepository


class AlternativeAnswerRepository(TenantScopedRepository[AlternativeAnswer]):
    search_fields: tuple[str, ...] = ("content",)
    sortable_fields = ("created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AlternativeAnswer, session)
