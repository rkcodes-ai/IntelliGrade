"""Persistence access for `AnswerEvaluation`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer_evaluation import AnswerEvaluation
from app.repositories.tenant_repository import TenantScopedRepository


class AnswerEvaluationRepository(TenantScopedRepository[AnswerEvaluation]):
    sortable_fields = ("created_at", "updated_at", "confidence_score", "review_status")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AnswerEvaluation, session)

    async def get_by_session_and_question(
        self,
        institution_id: uuid.UUID,
        exam_session_id: uuid.UUID,
        extracted_question_id: uuid.UUID,
    ) -> AnswerEvaluation | None:
        query = select(AnswerEvaluation).where(
            AnswerEvaluation.institution_id == institution_id,
            AnswerEvaluation.exam_session_id == exam_session_id,
            AnswerEvaluation.extracted_question_id == extracted_question_id,
            AnswerEvaluation.deleted_at.is_(None),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
