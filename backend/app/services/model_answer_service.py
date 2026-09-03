"""ModelAnswer management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError
from app.models.model_answer import ModelAnswer
from app.repositories.model_answer_repository import ModelAnswerRepository
from app.schemas.model_answer import ModelAnswerCreate, ModelAnswerUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class ModelAnswerService(TenantScopedService[ModelAnswer]):
    resource_type = "model_answer"

    def __init__(
        self,
        session: AsyncSession,
        repo: ModelAnswerRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or ModelAnswerRepository(session), audit_service=audit_service
        )

    async def create(
        self, institution_id: uuid.UUID, data: ModelAnswerCreate, *, created_by: uuid.UUID | None
    ) -> ModelAnswer:
        # Local import: `AnswerKey`/`AnswerKeyRepository` is a sibling
        # entity built in this same wave, kept local for consistency with
        # every other cross-entity parent lookup in this wave (see
        # `ClassScheduleService.create`'s `SubjectAllocationRepository`
        # import for the reasoning).
        from app.repositories.answer_key_repository import AnswerKeyRepository

        answer_key = await AnswerKeyRepository(self.session).get_by_id_for_institution(
            data.answer_key_id, institution_id
        )
        if answer_key is None:
            raise NotFoundError("Answer key not found.")

        model_answer = ModelAnswer(
            institution_id=institution_id,
            **data.model_dump(),
            created_by=created_by,
        )
        model_answer = await self.repo.add(model_answer)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, model_answer.id)
        return model_answer

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: ModelAnswerUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> ModelAnswer:
        model_answer = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(model_answer, field, value)
        model_answer.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(model_answer)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, model_answer.id)
        return model_answer
