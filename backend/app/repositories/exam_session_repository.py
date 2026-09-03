"""Persistence access for `ExamSession`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam_session import ExamSession
from app.repositories.tenant_repository import TenantScopedRepository


class ExamSessionRepository(TenantScopedRepository[ExamSession]):
    search_fields: tuple[str, ...] = ()
    sortable_fields = ("status", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ExamSession, session)

    async def exists_for_exam_and_student(
        self,
        institution_id: uuid.UUID,
        exam_id: uuid.UUID,
        student_user_id: uuid.UUID,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Whether an active (non-deleted) session already exists for this
        `(exam_id, student_user_id)` pair — used by `ExamSessionService` to
        raise a clean 409 before the database's own unique constraint would
        otherwise surface as a raw integrity error.
        """
        query = select(ExamSession.id).where(
            ExamSession.institution_id == institution_id,
            ExamSession.exam_id == exam_id,
            ExamSession.student_user_id == student_user_id,
            ExamSession.deleted_at.is_(None),
        )
        if exclude_id is not None:
            query = query.where(ExamSession.id != exclude_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None
