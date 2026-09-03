"""Persistence access for `MarkSchemeRange`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mark_scheme_range import MarkSchemeRange
from app.repositories.tenant_repository import TenantScopedRepository


class MarkSchemeRangeRepository(TenantScopedRepository[MarkSchemeRange]):
    search_fields: tuple[str, ...] = ()
    sortable_fields = ("display_order", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(MarkSchemeRange, session)
