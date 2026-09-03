"""Persistence access for `QuestionPaperQuestionMapping`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_paper_question_mapping import QuestionPaperQuestionMapping
from app.repositories.tenant_repository import TenantScopedRepository


class QuestionPaperQuestionMappingRepository(TenantScopedRepository[QuestionPaperQuestionMapping]):
    search_fields: tuple[str, ...] = ()
    sortable_fields = ("order_index", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(QuestionPaperQuestionMapping, session)

    async def mapping_exists(
        self,
        institution_id: uuid.UUID,
        question_paper_section_id: uuid.UUID,
        question_id: uuid.UUID,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Whether a (non-deleted) mapping already places `question_id` into
        `question_paper_section_id` for this institution — enforces the
        `uq_qpqm_section_question` unique constraint at the service layer
        with a clean 409 before the DB would raise an IntegrityError.
        """
        query = select(QuestionPaperQuestionMapping.id).where(
            QuestionPaperQuestionMapping.institution_id == institution_id,
            QuestionPaperQuestionMapping.deleted_at.is_(None),
            QuestionPaperQuestionMapping.question_paper_section_id == question_paper_section_id,
            QuestionPaperQuestionMapping.question_id == question_id,
        )
        if exclude_id is not None:
            query = query.where(QuestionPaperQuestionMapping.id != exclude_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None
