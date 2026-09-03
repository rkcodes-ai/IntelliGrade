"""Persistence access for `AIReferenceAnswer`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_reference_answer import AIReferenceAnswer
from app.repositories.tenant_repository import TenantScopedRepository


class AIReferenceAnswerRepository(TenantScopedRepository[AIReferenceAnswer]):
    sortable_fields = ("created_at", "updated_at", "version", "status")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AIReferenceAnswer, session)

    async def get_current_for_question(
        self, institution_id: uuid.UUID, extracted_question_id: uuid.UUID
    ) -> AIReferenceAnswer | None:
        query = select(AIReferenceAnswer).where(
            AIReferenceAnswer.institution_id == institution_id,
            AIReferenceAnswer.extracted_question_id == extracted_question_id,
            AIReferenceAnswer.is_current.is_(True),
            AIReferenceAnswer.deleted_at.is_(None),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_versions(
        self, institution_id: uuid.UUID, extracted_question_id: uuid.UUID
    ) -> list[AIReferenceAnswer]:
        query = (
            select(AIReferenceAnswer)
            .where(
                AIReferenceAnswer.institution_id == institution_id,
                AIReferenceAnswer.extracted_question_id == extracted_question_id,
                AIReferenceAnswer.deleted_at.is_(None),
            )
            .order_by(AIReferenceAnswer.version.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_latest_version_number(
        self, institution_id: uuid.UUID, extracted_question_id: uuid.UUID
    ) -> int:
        versions = await self.list_versions(institution_id, extracted_question_id)
        return versions[0].version if versions else 0
