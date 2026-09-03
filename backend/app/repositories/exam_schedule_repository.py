"""Persistence access for `ExamSchedule`."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam_schedule import ExamSchedule
from app.repositories.tenant_repository import TenantScopedRepository


class ExamScheduleRepository(TenantScopedRepository[ExamSchedule]):
    search_fields: tuple[str, ...] = ()
    sortable_fields = ("start_time", "end_time", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ExamSchedule, session)

    async def list_for_room_in_range(
        self,
        institution_id: uuid.UUID,
        room_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> list[ExamSchedule]:
        """
        Active (non-deleted, `is_active=True`) schedule rows for a room
        whose `[start_time, end_time)` range overlaps the given range,
        optionally excluding one row's own id (for an update's
        self-exclusion). Two ranges `[a_start, a_end)` and
        `[b_start, b_end)` overlap iff `a_start < b_end AND b_start < a_end`
        — used by `ExamScheduleService` to run the room-double-booking
        overlap check.
        """
        query = select(ExamSchedule).where(
            ExamSchedule.institution_id == institution_id,
            ExamSchedule.room_id == room_id,
            ExamSchedule.is_active.is_(True),
            ExamSchedule.deleted_at.is_(None),
            ExamSchedule.start_time < end_time,
            ExamSchedule.end_time > start_time,
        )
        if exclude_id is not None:
            query = query.where(ExamSchedule.id != exclude_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())
