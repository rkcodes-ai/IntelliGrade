"""ReferenceNote management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError
from app.models.reference_note import ReferenceNote
from app.repositories.reference_note_repository import ReferenceNoteRepository
from app.schemas.reference_note import ReferenceNoteCreate, ReferenceNoteUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class ReferenceNoteService(TenantScopedService[ReferenceNote]):
    resource_type = "reference_note"

    def __init__(
        self,
        session: AsyncSession,
        repo: ReferenceNoteRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or ReferenceNoteRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: ReferenceNoteCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> ReferenceNote:
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

        reference_note = ReferenceNote(
            institution_id=institution_id,
            **data.model_dump(),
            created_by=created_by,
        )
        reference_note = await self.repo.add(reference_note)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, reference_note.id)
        return reference_note

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: ReferenceNoteUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> ReferenceNote:
        reference_note = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(reference_note, field, value)
        reference_note.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(reference_note)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, reference_note.id)
        return reference_note
