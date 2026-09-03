"""
Generic repository for non-tenant-scoped, platform-level catalog tables
(Module 05's `OCRProvider` is the first user — see ADR-028: an OCR engine
catalog is system/technical data, not per-institution content).

Mirrors `app.repositories.tenant_repository.TenantScopedRepository`'s
shape exactly (search/sort/pagination/soft-delete), minus the
`institution_id` filter every method there applies. If a second
non-tenant-scoped entity needs this pattern later, it subclasses this the
same way any Module 03/04 entity subclasses `TenantScopedRepository`.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.repositories.base import BaseRepository
from app.schemas.pagination import PageParams, SortOrder


class GlobalRepository[ModelType: Base](BaseRepository[ModelType]):
    search_fields: tuple[str, ...] = ()
    sortable_fields: tuple[str, ...] = ("created_at", "updated_at")

    def _base_query(self, *, include_deleted: bool = False) -> Select[Any]:
        query = select(self.model)
        if not include_deleted:
            query = query.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        return query

    def _apply_search(self, query: Select[Any], search: str | None) -> Select[Any]:
        if not search or not self.search_fields:
            return query
        pattern = f"%{search}%"
        conditions = [
            getattr(self.model, field).ilike(pattern)
            for field in self.search_fields
            if hasattr(self.model, field)
        ]
        return query.where(or_(*conditions)) if conditions else query

    def _apply_sort(self, query: Select[Any], params: PageParams) -> Select[Any]:
        field_name = params.sort_by if params.sort_by in self.sortable_fields else "created_at"
        column = getattr(self.model, field_name)
        return query.order_by(
            column.desc() if params.sort_order == SortOrder.DESC else column.asc()
        )

    async def get_by_id(
        self, entity_id: uuid.UUID, *, include_deleted: bool = False
    ) -> ModelType | None:
        query = self._base_query(include_deleted=include_deleted).where(
            self.model.id == entity_id  # type: ignore[attr-defined]
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_paginated(
        self, params: PageParams, *, extra_filters: Sequence[Any] = ()
    ) -> tuple[list[ModelType], int]:
        query = self._base_query()
        for condition in extra_filters:
            query = query.where(condition)
        query = self._apply_search(query, params.search)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar_one()

        query = self._apply_sort(query, params).limit(params.limit).offset(params.offset)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def list_deleted(self, params: PageParams) -> tuple[list[ModelType], int]:
        query = select(self.model).where(self.model.deleted_at.is_not(None))  # type: ignore[attr-defined]
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar_one()
        query = self._apply_sort(query, params).limit(params.limit).offset(params.offset)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def code_exists(
        self, code_field: str, code_value: str, *, exclude_id: uuid.UUID | None = None
    ) -> bool:
        column = getattr(self.model, code_field)
        query = select(self.model.id).where(  # type: ignore[attr-defined]
            self.model.deleted_at.is_(None), column == code_value  # type: ignore[attr-defined]
        )
        if exclude_id is not None:
            query = query.where(self.model.id != exclude_id)  # type: ignore[attr-defined]
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def soft_delete(self, entity: ModelType, *, actor_id: uuid.UUID | None) -> None:
        entity.mark_deleted()  # type: ignore[attr-defined]
        entity.updated_by = actor_id  # type: ignore[attr-defined]
        await self.session.flush()

    async def restore(self, entity: ModelType, *, actor_id: uuid.UUID | None) -> None:
        entity.restore()  # type: ignore[attr-defined]
        entity.updated_by = actor_id  # type: ignore[attr-defined]
        await self.session.flush()

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        super().__init__(model, session)
