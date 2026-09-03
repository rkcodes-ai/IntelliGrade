"""Persistence access for `QuestionTagMap`.

Plain `BaseRepository`-style, not `TenantScopedRepository` — this is a
lightweight junction table (see `app/models/question_tag_map.py`), so it
doesn't need soft-delete-aware querying, search, or pagination. The
institution scope is enforced by the caller (`QuestionService`), which
already resolves `Question` and `QuestionTag` through their own
tenant-scoped repositories before touching a mapping row.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_tag_map import QuestionTagMap
from app.repositories.base import BaseRepository


class QuestionTagMapRepository(BaseRepository[QuestionTagMap]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(QuestionTagMap, session)

    async def get_by_question_and_tag(
        self, question_id: uuid.UUID, tag_id: uuid.UUID
    ) -> QuestionTagMap | None:
        query = select(QuestionTagMap).where(
            QuestionTagMap.question_id == question_id,
            QuestionTagMap.tag_id == tag_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def remove(self, entity: QuestionTagMap) -> None:
        await self.delete(entity)
