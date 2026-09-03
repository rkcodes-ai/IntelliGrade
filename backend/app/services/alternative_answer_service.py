"""AlternativeAnswer management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError
from app.models.alternative_answer import AlternativeAnswer
from app.repositories.alternative_answer_repository import AlternativeAnswerRepository
from app.schemas.alternative_answer import AlternativeAnswerCreate, AlternativeAnswerUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class AlternativeAnswerService(TenantScopedService[AlternativeAnswer]):
    resource_type = "alternative_answer"

    def __init__(
        self,
        session: AsyncSession,
        repo: AlternativeAnswerRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or AlternativeAnswerRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: AlternativeAnswerCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> AlternativeAnswer:
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

        alternative_answer = AlternativeAnswer(
            institution_id=institution_id,
            **data.model_dump(),
            created_by=created_by,
        )
        alternative_answer = await self.repo.add(alternative_answer)
        await self._log_audit(
            AuditAction.ACADEMIC_ENTITY_CREATED, created_by, alternative_answer.id
        )
        return alternative_answer

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: AlternativeAnswerUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> AlternativeAnswer:
        alternative_answer = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(alternative_answer, field, value)
        alternative_answer.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(alternative_answer)

        await self._log_audit(
            AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, alternative_answer.id
        )
        return alternative_answer
