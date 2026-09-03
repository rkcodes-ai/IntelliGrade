"""
Persistence access for `Institution` — the one academic repository that
is NOT tenant-scoped (it IS the tenant). Structured like
`TenantScopedRepository` (search/sort/paginate/soft-delete/restore) but
without an `institution_id` filter, since `Institution` has none.
"""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.institution import Institution
from app.models.user_institution import UserInstitution
from app.repositories.base import BaseRepository
from app.schemas.pagination import PageParams, SortOrder

_SEARCH_FIELDS = ("name", "code")
_SORTABLE_FIELDS = ("name", "code", "created_at", "updated_at")


class InstitutionRepository(BaseRepository[Institution]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Institution, session)

    async def get_by_id(self, entity_id: uuid.UUID) -> Institution | None:
        result = await self.session.execute(
            select(Institution).where(Institution.id == entity_id, Institution.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_id_include_deleted(self, entity_id: uuid.UUID) -> Institution | None:
        return await self.session.get(Institution, entity_id)

    async def name_exists(self, name: str, *, exclude_id: uuid.UUID | None = None) -> bool:
        query = select(Institution.id).where(
            Institution.name == name, Institution.deleted_at.is_(None)
        )
        if exclude_id is not None:
            query = query.where(Institution.id != exclude_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def code_exists(self, code: str, *, exclude_id: uuid.UUID | None = None) -> bool:
        query = select(Institution.id).where(
            Institution.code == code, Institution.deleted_at.is_(None)
        )
        if exclude_id is not None:
            query = query.where(Institution.id != exclude_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def list_paginated(self, params: PageParams) -> tuple[list[Institution], int]:
        query = select(Institution).where(Institution.deleted_at.is_(None))
        if params.search:
            pattern = f"%{params.search}%"
            query = query.where(
                or_(*(getattr(Institution, f).ilike(pattern) for f in _SEARCH_FIELDS))
            )
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar_one()

        field_name = params.sort_by if params.sort_by in _SORTABLE_FIELDS else "created_at"
        column = getattr(Institution, field_name)
        query = query.order_by(
            column.desc() if params.sort_order == SortOrder.DESC else column.asc()
        )
        query = query.limit(params.limit).offset(params.offset)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def list_deleted(self, params: PageParams) -> tuple[list[Institution], int]:
        query = select(Institution).where(Institution.deleted_at.is_not(None))
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar_one()
        field_name = params.sort_by if params.sort_by in _SORTABLE_FIELDS else "created_at"
        column = getattr(Institution, field_name)
        query = query.order_by(
            column.desc() if params.sort_order == SortOrder.DESC else column.asc()
        )
        query = query.limit(params.limit).offset(params.offset)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def list_all_active(self) -> list[Institution]:
        result = await self.session.execute(
            select(Institution)
            .where(Institution.deleted_at.is_(None))
            .order_by(Institution.name.asc())
        )
        return list(result.scalars().all())

    async def list_for_user(self, user_id: uuid.UUID) -> list[Institution]:
        result = await self.session.execute(
            select(Institution)
            .join(UserInstitution, UserInstitution.institution_id == Institution.id)
            .where(
                UserInstitution.user_id == user_id,
                UserInstitution.is_active.is_(True),
                Institution.deleted_at.is_(None),
            )
            .order_by(Institution.name.asc())
        )
        return list(result.scalars().all())

    async def soft_delete(self, entity: Institution, *, actor_id: uuid.UUID | None) -> None:
        entity.mark_deleted()
        entity.is_active = False
        entity.updated_by = actor_id
        await self.session.flush()

    async def restore(self, entity: Institution, *, actor_id: uuid.UUID | None) -> None:
        entity.restore()
        entity.updated_by = actor_id
        await self.session.flush()
