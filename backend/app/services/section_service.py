"""
Section management service.

Business rules enforced here (not in the database): `batch_id` must exist
for the institution and `name` must be unique per batch.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.section import Section
from app.repositories.batch_repository import BatchRepository
from app.repositories.section_repository import SectionRepository
from app.schemas.section import SectionCreate, SectionUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class SectionService(TenantScopedService[Section]):
    resource_type = "section"

    def __init__(
        self,
        session: AsyncSession,
        repo: SectionRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session, repo or SectionRepository(session), audit_service=audit_service)

    async def _assert_batch_exists(self, institution_id: uuid.UUID, batch_id: uuid.UUID) -> None:
        batch = await BatchRepository(self.session).get_by_id_for_institution(
            batch_id, institution_id
        )
        if batch is None:
            raise NotFoundError("Batch not found.")

    async def create(
        self, institution_id: uuid.UUID, data: SectionCreate, *, created_by: uuid.UUID | None
    ) -> Section:
        await self._assert_batch_exists(institution_id, data.batch_id)

        if await self.repo.code_exists(
            institution_id,
            "name",
            data.name,
            scope_conditions=(Section.batch_id == data.batch_id,),
        ):
            raise ConflictError("A section with that name already exists for this batch.")

        section = Section(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        section = await self.repo.add(section)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, section.id)
        return section

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: SectionUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> Section:
        section = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        target_batch_id = updates.get("batch_id", section.batch_id)

        if "batch_id" in updates:
            await self._assert_batch_exists(institution_id, target_batch_id)

        if "name" in updates or "batch_id" in updates:
            name_value = updates.get("name", section.name)
            if await self.repo.code_exists(
                institution_id,
                "name",
                name_value,
                exclude_id=entity_id,
                scope_conditions=(Section.batch_id == target_batch_id,),
            ):
                raise ConflictError("A section with that name already exists for this batch.")

        for field, value in updates.items():
            setattr(section, field, value)
        section.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(section)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, section.id)
        return section
