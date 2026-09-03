"""
Generic service base pairing `app.repositories.global_repository.
GlobalRepository` — see that module's docstring and ADR-028. Mirrors
`app.services.tenant_service.TenantScopedService` minus every
`institution_id` parameter.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.base import Base
from app.repositories.global_repository import GlobalRepository
from app.schemas.pagination import Page, PageParams
from app.services.audit_service import AuditService
from app.services.base import BaseService


class GlobalService[ModelType: Base](BaseService):
    resource_type: str = "resource"

    def __init__(
        self,
        session: AsyncSession,
        repo: GlobalRepository[ModelType],
        *,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session)
        self.repo = repo
        self.audit_service = audit_service or AuditService(session)

    async def get_by_id(
        self, entity_id: uuid.UUID, *, not_found_message: str | None = None
    ) -> ModelType:
        entity = await self.repo.get_by_id(entity_id)
        if entity is None:
            raise NotFoundError(not_found_message or f"{self.resource_type.title()} not found.")
        return entity

    async def list_paginated(
        self, params: PageParams, *, extra_filters: tuple[Any, ...] = ()
    ) -> tuple[list[ModelType], int]:
        return await self.repo.list_paginated(params, extra_filters=extra_filters)

    async def list_deleted(self, params: PageParams) -> tuple[list[ModelType], int]:
        return await self.repo.list_deleted(params)

    async def soft_delete(
        self, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None, action: str
    ) -> None:
        entity = await self.get_by_id(entity_id)
        await self.repo.soft_delete(entity, actor_id=actor_id)
        await self._log_audit(action, actor_id, entity_id)

    async def restore(
        self, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None, action: str
    ) -> ModelType:
        entity = await self.repo.get_by_id(entity_id, include_deleted=True)
        if entity is None:
            raise NotFoundError(f"{self.resource_type.title()} not found.")
        await self.repo.restore(entity, actor_id=actor_id)
        await self.session.refresh(entity)  # see TenantScopedService.restore's MissingGreenlet note
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
