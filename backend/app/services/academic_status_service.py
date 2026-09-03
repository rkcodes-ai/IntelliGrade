"""AcademicStatus management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError
from app.models.academic_status import AcademicStatus
from app.repositories.academic_status_repository import AcademicStatusRepository
from app.schemas.academic_status import AcademicStatusCreate, AcademicStatusUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class AcademicStatusService(TenantScopedService[AcademicStatus]):
    resource_type = "academic_status"

    def __init__(
        self,
        session: AsyncSession,
        repo: AcademicStatusRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or AcademicStatusRepository(session), audit_service=audit_service
        )

    async def create(
        self, institution_id: uuid.UUID, data: AcademicStatusCreate, *, created_by: uuid.UUID | None
    ) -> AcademicStatus:
        if await self.repo.code_exists(institution_id, "code", data.code):
            raise ConflictError("An academic status with that code already exists.")

        entity = AcademicStatus(
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
        data: AcademicStatusUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> AcademicStatus:
        entity = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "code" in updates and await self.repo.code_exists(
            institution_id, "code", updates["code"], exclude_id=entity_id
        ):
            raise ConflictError("An academic status with that code already exists.")

        for field, value in updates.items():
            setattr(entity, field, value)
        entity.updated_by = updated_by
        await self.session.flush()
        # See `SubjectCategoryService.update` for why this refresh is needed
        # (avoids a post-flush `MissingGreenlet` on `updated_at`).
        await self.session.refresh(entity)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, entity.id)
        return entity
