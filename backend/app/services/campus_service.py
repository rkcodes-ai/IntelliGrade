"""Campus management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError
from app.models.campus import Campus
from app.repositories.campus_repository import CampusRepository
from app.schemas.campus import CampusCreate, CampusUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class CampusService(TenantScopedService[Campus]):
    resource_type = "campus"

    def __init__(
        self,
        session: AsyncSession,
        repo: CampusRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session, repo or CampusRepository(session), audit_service=audit_service)

    async def create(
        self, institution_id: uuid.UUID, data: CampusCreate, *, created_by: uuid.UUID | None
    ) -> Campus:
        if await self.repo.code_exists(institution_id, "code", data.code):
            raise ConflictError("A campus with that code already exists.")

        campus = Campus(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        campus = await self.repo.add(campus)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, campus.id)
        return campus

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: CampusUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> Campus:
        campus = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "code" in updates and await self.repo.code_exists(
            institution_id, "code", updates["code"], exclude_id=entity_id
        ):
            raise ConflictError("A campus with that code already exists.")

        for field, value in updates.items():
            setattr(campus, field, value)
        campus.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(campus)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, campus.id)
        return campus
