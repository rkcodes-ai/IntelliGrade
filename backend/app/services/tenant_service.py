"""
Generic tenant-scoped service base for the Academic Domain (Module 03).

Subclasses `app.services.base.BaseService` unchanged (imported, not copied
— see ADR-017). Provides the read/list/soft-delete/restore operations that
are identical across all 20 academic entities, plus an audit-logging
convenience wrapper. `create`/`update` are intentionally NOT generic here
— every entity has distinct validation (duplicate codes, parent-ownership,
date-overlap rules), so those stay in each concrete service, following
Module 02's `UserService` pattern exactly.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.base import Base
from app.repositories.tenant_repository import TenantScopedRepository
from app.schemas.pagination import Page, PageParams
from app.services.audit_service import AuditService
from app.services.base import BaseService


class TenantScopedService[ModelType: Base](BaseService):
    #: Human-readable resource type recorded on audit log entries, e.g. "campus".
    resource_type: str = "resource"

    def __init__(
        self,
        session: AsyncSession,
        repo: TenantScopedRepository[ModelType],
        *,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session)
        self.repo = repo
        self.audit_service = audit_service or AuditService(session)

    async def get_by_id(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        *,
        not_found_message: str | None = None,
    ) -> ModelType:
        entity = await self.repo.get_by_id_for_institution(entity_id, institution_id)
        if entity is None:
            raise NotFoundError(not_found_message or f"{self.resource_type.title()} not found.")
        return entity

    async def list_paginated(
        self, institution_id: uuid.UUID, params: PageParams, *, extra_filters: tuple[Any, ...] = ()
    ) -> tuple[list[ModelType], int]:
        return await self.repo.list_paginated(institution_id, params, extra_filters=extra_filters)

    async def list_deleted(
        self, institution_id: uuid.UUID, params: PageParams
    ) -> tuple[list[ModelType], int]:
        return await self.repo.list_deleted(institution_id, params)

    async def soft_delete(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        *,
        actor_id: uuid.UUID | None,
        action: str,
    ) -> None:
        entity = await self.get_by_id(institution_id, entity_id)
        await self.repo.soft_delete(entity, actor_id=actor_id)
        await self._log_audit(action, actor_id, entity_id)

    async def restore(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        *,
        actor_id: uuid.UUID | None,
        action: str,
    ) -> ModelType:
        entity = await self.repo.get_by_id_for_institution(
            entity_id, institution_id, include_deleted=True
        )
        if entity is None:
            raise NotFoundError(f"{self.resource_type.title()} not found.")
        await self.repo.restore(entity, actor_id=actor_id)
        # `updated_at` (TimestampMixin's onupdate=func.now()) is left "expired"
        # by SQLAlchemy after an UPDATE flush — SQLite/aiosqlite doesn't use
        # RETURNING for UPDATE the way it does for INSERT. A synchronous
        # Pydantic read of that attribute during response serialization would
        # otherwise trigger an implicit lazy-refresh outside greenlet context
        # (MissingGreenlet). Refreshing here, once, centrally, fixes every
        # entity's restore response — found during Module 03 implementation.
        await self.session.refresh(entity)
        await self._log_audit(action, actor_id, entity_id)
        return entity

    async def _log_audit(
        self,
        action: str,
        actor_id: uuid.UUID | None,
        resource_id: uuid.UUID | str,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        await self.audit_service.log(
            action=action,
            status="success",
            user_id=actor_id,
            resource_type=self.resource_type,
            resource_id=str(resource_id),
            context=context,
        )

    @staticmethod
    def to_page(items: list[ModelType], total: int, params: PageParams, mapper: Any) -> Page[Any]:
        return Page.create([mapper(item) for item in items], total=total, params=params)
