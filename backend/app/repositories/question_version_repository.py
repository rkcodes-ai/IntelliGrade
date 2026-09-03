"""Persistence access for `QuestionVersion`."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_version import QuestionVersion
from app.repositories.tenant_repository import TenantScopedRepository


class QuestionVersionRepository(TenantScopedRepository[QuestionVersion]):
    search_fields = ("question_text", "change_reason")
    sortable_fields = ("created_at", "updated_at", "version_number")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(QuestionVersion, session)

    async def get_next_version_number(self, question_id: uuid.UUID) -> int:
        """`max(version_number) + 1` across all snapshots of this question, or 1 if none exist."""
        query = select(func.max(QuestionVersion.version_number)).where(
            QuestionVersion.question_id == question_id
        )
        result = await self.session.execute(query)
        current_max = result.scalar_one_or_none()
        return (current_max or 0) + 1
