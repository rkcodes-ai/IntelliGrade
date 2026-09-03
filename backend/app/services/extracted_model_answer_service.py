"""
ExtractedModelAnswer management service (Module 06).

Rows are written internally by `app.tasks.official_document_tasks`
(the OCR/AI extraction pipeline) — this service never creates rows, only
reads/updates/verifies the ones the pipeline already wrote.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.models.extracted_model_answer import ExtractedModelAnswer
from app.repositories.extracted_model_answer_repository import ExtractedModelAnswerRepository
from app.schemas.extracted_model_answer import ExtractedModelAnswerUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class ExtractedModelAnswerService(TenantScopedService[ExtractedModelAnswer]):
    resource_type = "extracted_model_answer"

    def __init__(
        self,
        session: AsyncSession,
        repo: ExtractedModelAnswerRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or ExtractedModelAnswerRepository(session), audit_service=audit_service
        )

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: ExtractedModelAnswerUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> ExtractedModelAnswer:
        entity = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(entity, field, value)
        entity.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(entity)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, entity.id)
        return entity

    async def verify(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> ExtractedModelAnswer:
        entity = await self.get_by_id(institution_id, entity_id)
        entity.verification_status = "verified"
        entity.verified_by = actor_id
        entity.verified_at = datetime.now(UTC)
        entity.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(entity)
        await self._log_audit(AuditAction.EXTRACTED_MODEL_ANSWER_VERIFIED, actor_id, entity.id)
        return entity
