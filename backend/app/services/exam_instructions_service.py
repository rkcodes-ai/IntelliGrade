"""ExamInstructions management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError
from app.models.exam_instructions import ExamInstructions
from app.repositories.exam_instructions_repository import ExamInstructionsRepository
from app.schemas.exam_instructions import ExamInstructionsCreate, ExamInstructionsUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class ExamInstructionsService(TenantScopedService[ExamInstructions]):
    resource_type = "exam_instructions"

    def __init__(
        self,
        session: AsyncSession,
        repo: ExamInstructionsRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or ExamInstructionsRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: ExamInstructionsCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> ExamInstructions:
        # Local import: `ExamRepository` is a same-wave sibling and may not
        # exist on disk yet when this module is first imported — kept local
        # so this file stays importable regardless of import order (same
        # pattern as `class_schedule_service.py`).
        from app.repositories.exam_repository import ExamRepository

        exam = await ExamRepository(self.session).get_by_id_for_institution(
            data.exam_id, institution_id
        )
        if exam is None:
            raise NotFoundError("Exam not found.")

        instructions = ExamInstructions(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        instructions = await self.repo.add(instructions)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, instructions.id)
        return instructions

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: ExamInstructionsUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> ExamInstructions:
        from app.repositories.exam_repository import ExamRepository

        instructions = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "exam_id" in updates:
            exam = await ExamRepository(self.session).get_by_id_for_institution(
                updates["exam_id"], institution_id
            )
            if exam is None:
                raise NotFoundError("Exam not found.")

        for field, value in updates.items():
            setattr(instructions, field, value)
        instructions.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(instructions)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, instructions.id)
        return instructions
