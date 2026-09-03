"""BloomTaxonomyLevel management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError
from app.models.bloom_taxonomy_level import BloomTaxonomyLevel
from app.repositories.bloom_taxonomy_level_repository import BloomTaxonomyLevelRepository
from app.schemas.bloom_taxonomy_level import BloomTaxonomyLevelCreate, BloomTaxonomyLevelUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class BloomTaxonomyLevelService(TenantScopedService[BloomTaxonomyLevel]):
    resource_type = "bloom_taxonomy_level"

    def __init__(
        self,
        session: AsyncSession,
        repo: BloomTaxonomyLevelRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or BloomTaxonomyLevelRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: BloomTaxonomyLevelCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> BloomTaxonomyLevel:
        if await self.repo.code_exists(institution_id, "code", data.code):
            raise ConflictError("A Bloom's taxonomy level with that code already exists.")

        entity = BloomTaxonomyLevel(
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
        data: BloomTaxonomyLevelUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> BloomTaxonomyLevel:
        entity = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "code" in updates and await self.repo.code_exists(
            institution_id, "code", updates["code"], exclude_id=entity_id
        ):
            raise ConflictError("A Bloom's taxonomy level with that code already exists.")

        for field, value in updates.items():
            setattr(entity, field, value)
        entity.updated_by = updated_by
        await self.session.flush()
        # `updated_at` (onupdate=func.now()) is left expired by the flush on
        # SQLite/aiosqlite (no eager RETURNING fetch on UPDATE) — refresh here,
        # while still inside an awaited session call, so the later synchronous
        # Pydantic read in the router's `_to_read()` doesn't trigger a lazy
        # load outside of greenlet context (`MissingGreenlet`).
        await self.session.refresh(entity)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, entity.id)
        return entity
