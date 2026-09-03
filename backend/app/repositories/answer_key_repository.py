"""Persistence access for `AnswerKey`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer_key import AnswerKey
from app.repositories.tenant_repository import TenantScopedRepository


class AnswerKeyRepository(TenantScopedRepository[AnswerKey]):
    search_fields: tuple[str, ...] = ("reference_answer", "evaluation_notes")
    sortable_fields = ("created_at", "updated_at", "current_version")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AnswerKey, session)
