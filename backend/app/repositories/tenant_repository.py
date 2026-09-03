"""
Generic tenant-scoped repository for the Academic Domain (Module 03).

Subclasses `app.repositories.base.BaseRepository` unchanged (imported, not
copied — see ADR-017) and adds the cross-cutting behavior every academic
entity needs: institution filtering, soft-delete-aware queries, search,
sort, and pagination. A concrete repository is typically <40 lines:

    class CampusRepository(TenantScopedRepository[Campus]):
        search_fields = ("name", "code")

        def __init__(self, session: AsyncSession) -> None:
            super().__init__(Campus, session)
"""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.repositories.base import BaseRepository
from app.schemas.pagination import PageParams, SortOrder


class TenantScopedRepository[ModelType: Base](BaseRepository[ModelType]):
    """
    Every query method here is scoped to a single `institution_id` and,
    by default, excludes soft-deleted rows. This is the one place tenant
    isolation is implemented for the Academic Domain — concrete
    repositories should never hand-roll their own `institution_id` filter.
    """

    #: Column names (on `ModelType`) searched (case-insensitive, OR'd) when
    #: `PageParams.search` is set. Override in subclasses.
    search_fields: tuple[str, ...] = ()

    #: Column names allowed as `PageParams.sort_by`. Falls back to
    #: `created_at` if the requested field isn't in this allowlist —
    #: prevents sorting by an arbitrary/non-indexed or sensitive column.
    sortable_fields: tuple[str, ...] = ("created_at", "updated_at")

    def _base_query(
        self, institution_id: uuid.UUID, *, include_deleted: bool = False
    ) -> Select[Any]:
        # ModelType is bound to `Base` (inherited from BaseRepository[ModelType]), which
        # doesn't itself declare institution_id/deleted_at/id — those come from mixins
        # applied per-concrete-model (InstitutionOwnedMixin/SoftDeleteMixin/
        # UUIDPrimaryKeyMixin). Every model TenantScopedRepository is used with composes
        # all three, so these accesses are safe at runtime; mypy can't see that through
        # the generic bound, hence the targeted ignores below.
        query = select(self.model).where(self.model.institution_id == institution_id)  # type: ignore[attr-defined]
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

    async def get_by_id_for_institution(
        self, entity_id: uuid.UUID, institution_id: uuid.UUID, *, include_deleted: bool = False
    ) -> ModelType | None:
        query = self._base_query(institution_id, include_deleted=include_deleted).where(
            self.model.id == entity_id  # type: ignore[attr-defined]
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_paginated(
        self, institution_id: uuid.UUID, params: PageParams, *, extra_filters: Sequence[Any] = ()
    ) -> tuple[list[ModelType], int]:
        query = self._base_query(institution_id)
        for condition in extra_filters:
            query = query.where(condition)
        query = self._apply_search(query, params.search)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar_one()

        query = self._apply_sort(query, params).limit(params.limit).offset(params.offset)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def list_deleted(
        self, institution_id: uuid.UUID, params: PageParams
    ) -> tuple[list[ModelType], int]:
        """Soft-deleted rows only — powers the admin 'restore' UI."""
        query = select(self.model).where(
            self.model.institution_id == institution_id,  # type: ignore[attr-defined]
            self.model.deleted_at.is_not(None),  # type: ignore[attr-defined]
        )
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar_one()
        query = self._apply_sort(query, params).limit(params.limit).offset(params.offset)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def code_exists(
        self,
        institution_id: uuid.UUID,
        code_field: str,
        code_value: str,
        *,
        exclude_id: uuid.UUID | None = None,
        scope_conditions: Sequence[Any] = (),
    ) -> bool:
        """
        Duplicate-code check scoped to institution (+ optional extra scope,
        e.g. `campus_id == X` for a code that must be unique per-campus
        rather than per-institution). Used by every entity's
        create/update validation (see e.g. `CampusService.create`).
        """
        column = getattr(self.model, code_field)
        query = select(self.model.id).where(  # type: ignore[attr-defined]
            self.model.institution_id == institution_id,  # type: ignore[attr-defined]
            self.model.deleted_at.is_(None),  # type: ignore[attr-defined]
            column == code_value,
        )
        for condition in scope_conditions:
            query = query.where(condition)
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
