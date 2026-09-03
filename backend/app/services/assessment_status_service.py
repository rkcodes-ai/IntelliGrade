"""AssessmentStatus management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError
from app.models.assessment_status import AssessmentStatus
from app.repositories.assessment_status_repository import AssessmentStatusRepository
from app.schemas.assessment_status import AssessmentStatusCreate, AssessmentStatusUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class AssessmentStatusService(TenantScopedService[AssessmentStatus]):
    resource_type = "assessment_status"

    def __init__(
        self,
        session: AsyncSession,
        repo: AssessmentStatusRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or AssessmentStatusRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: AssessmentStatusCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> AssessmentStatus:
        if await self.repo.code_exists(institution_id, "code", data.code):
            raise ConflictError("An assessment status with that code already exists.")

        entity = AssessmentStatus(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        entity = await self.repo.add(entity)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, entity.id)
        return entity

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: AssessmentStatusUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> AssessmentStatus:
        entity = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "code" in updates and await self.repo.code_exists(
            institution_id, "code", updates["code"], exclude_id=entity_id
        ):
            raise ConflictError("An assessment status with that code already exists.")

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
