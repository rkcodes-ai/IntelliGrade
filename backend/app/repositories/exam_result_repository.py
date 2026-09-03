"""Persistence access for `ExamResult` (Module 07)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam_result import ExamResult
from app.repositories.tenant_repository import TenantScopedRepository


class ExamResultRepository(TenantScopedRepository[ExamResult]):
    sortable_fields = ("created_at", "updated_at", "status", "total_marks")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ExamResult, session)

    async def get_by_exam_session(
        self, institution_id: uuid.UUID, exam_session_id: uuid.UUID
    ) -> ExamResult | None:
        query = select(ExamResult).where(
            ExamResult.institution_id == institution_id,
            ExamResult.exam_session_id == exam_session_id,
            ExamResult.deleted_at.is_(None),
        )
        return (await self.session.execute(query)).scalar_one_or_none()
