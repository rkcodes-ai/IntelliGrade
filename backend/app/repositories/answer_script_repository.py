"""Persistence access for `AnswerScript`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer_script import AnswerScript
from app.repositories.tenant_repository import TenantScopedRepository


class AnswerScriptRepository(TenantScopedRepository[AnswerScript]):
    search_fields: tuple[str, ...] = ("original_filename",)
    sortable_fields = ("status", "created_at", "updated_at", "page_count")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AnswerScript, session)

    async def find_duplicate(
        self, institution_id: uuid.UUID, exam_session_id: uuid.UUID, checksum_sha256: str
    ) -> AnswerScript | None:
        """Duplicate-upload detection: an active (non-deleted) script with
        the same checksum already exists for this exam session."""
        query = select(AnswerScript).where(
            AnswerScript.institution_id == institution_id,
            AnswerScript.exam_session_id == exam_session_id,
            AnswerScript.checksum_sha256 == checksum_sha256,
            AnswerScript.deleted_at.is_(None),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
