"""Persistence access for `QuestionPaperVersion`."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_paper_version import QuestionPaperVersion
from app.repositories.tenant_repository import TenantScopedRepository


class QuestionPaperVersionRepository(TenantScopedRepository[QuestionPaperVersion]):
    search_fields = ()
    sortable_fields = ("version_number", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(QuestionPaperVersion, session)

    async def get_next_version_number(
        self, institution_id: uuid.UUID, question_paper_id: uuid.UUID
    ) -> int:
        """The parent paper's current max `version_number` + 1, or 1 if this
        is its first snapshot."""
        query = select(func.max(self.model.version_number)).where(
            self.model.institution_id == institution_id,
            self.model.question_paper_id == question_paper_id,
        )
        result = await self.session.execute(query)
        current_max = result.scalar_one_or_none()
        return (current_max or 0) + 1
