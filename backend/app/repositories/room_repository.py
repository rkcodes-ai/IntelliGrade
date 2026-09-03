"""Persistence access for `Room`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.room import Room
from app.repositories.tenant_repository import TenantScopedRepository


class RoomRepository(TenantScopedRepository[Room]):
    search_fields = ("name", "building")
    sortable_fields = ("name", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Room, session)
