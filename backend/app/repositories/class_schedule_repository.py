"""Persistence access for `ClassSchedule`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_schedule import ClassSchedule
from app.repositories.tenant_repository import TenantScopedRepository


class ClassScheduleRepository(TenantScopedRepository[ClassSchedule]):
    search_fields: tuple[str, ...] = ()
    sortable_fields = ("day_of_week", "start_time", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ClassSchedule, session)

    async def list_for_room_and_day(
        self,
        institution_id: uuid.UUID,
        room_id: uuid.UUID,
        day_of_week: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> list[ClassSchedule]:
        """
        All active (non-deleted, `is_active=True`) schedule rows for a room
        on a given day, optionally excluding one row's own id (for an
        update's self-exclusion). Used by `ClassScheduleService` to run the
        room-double-booking overlap check.
        """
        query = select(ClassSchedule).where(
            ClassSchedule.institution_id == institution_id,
            ClassSchedule.room_id == room_id,
            ClassSchedule.day_of_week == day_of_week,
            ClassSchedule.is_active.is_(True),
            ClassSchedule.deleted_at.is_(None),
        )
        if exclude_id is not None:
            query = query.where(ClassSchedule.id != exclude_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())
