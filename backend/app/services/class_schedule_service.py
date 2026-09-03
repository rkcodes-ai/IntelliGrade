"""ClassSchedule management service."""

import uuid
from datetime import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.class_schedule import ClassSchedule
from app.repositories.class_schedule_repository import ClassScheduleRepository
from app.repositories.room_repository import RoomRepository
from app.schemas.class_schedule import ClassScheduleCreate, ClassScheduleUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class ClassScheduleService(TenantScopedService[ClassSchedule]):
    resource_type = "class_schedule"

    def __init__(
        self,
        session: AsyncSession,
        repo: ClassScheduleRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        repo = repo or ClassScheduleRepository(session)
        super().__init__(session, repo, audit_service=audit_service)
        self._class_schedule_repo = repo

    async def create(
        self, institution_id: uuid.UUID, data: ClassScheduleCreate, *, created_by: uuid.UUID | None
    ) -> ClassSchedule:
        # Local import: SubjectAllocation is owned by a sibling agent in
        # this same wave and may not exist on disk yet when this module is
        # first imported — kept local so this file stays importable
        # regardless of import order.
        from app.repositories.subject_allocation_repository import SubjectAllocationRepository

        allocation = await SubjectAllocationRepository(self.session).get_by_id_for_institution(
            data.subject_allocation_id, institution_id
        )
        if allocation is None:
            raise NotFoundError("Subject allocation not found.")

        room = await RoomRepository(self.session).get_by_id_for_institution(
            data.room_id, institution_id
        )
        if room is None:
            raise NotFoundError("Room not found.")

        if data.start_time >= data.end_time:
            raise ValidationAppError("start_time must be before end_time.")

        await self._assert_no_overlap(
            institution_id, data.room_id, data.day_of_week, data.start_time, data.end_time
        )

        schedule = ClassSchedule(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        schedule = await self.repo.add(schedule)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, schedule.id)
        return schedule

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: ClassScheduleUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> ClassSchedule:
        from app.repositories.subject_allocation_repository import SubjectAllocationRepository

        schedule = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "subject_allocation_id" in updates:
            allocation = await SubjectAllocationRepository(self.session).get_by_id_for_institution(
                updates["subject_allocation_id"], institution_id
            )
            if allocation is None:
                raise NotFoundError("Subject allocation not found.")

        if "room_id" in updates:
            room = await RoomRepository(self.session).get_by_id_for_institution(
                updates["room_id"], institution_id
            )
            if room is None:
                raise NotFoundError("Room not found.")

        target_room_id = updates.get("room_id", schedule.room_id)
        target_day = updates.get("day_of_week", schedule.day_of_week)
        target_start = updates.get("start_time", schedule.start_time)
        target_end = updates.get("end_time", schedule.end_time)

        if target_start >= target_end:
            raise ValidationAppError("start_time must be before end_time.")

        if any(f in updates for f in ("room_id", "day_of_week", "start_time", "end_time")):
            await self._assert_no_overlap(
                institution_id,
                target_room_id,
                target_day,
                target_start,
                target_end,
                exclude_id=entity_id,
            )

        for field, value in updates.items():
            setattr(schedule, field, value)
        schedule.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(schedule)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, schedule.id)
        return schedule

    async def _assert_no_overlap(
        self,
        institution_id: uuid.UUID,
        room_id: uuid.UUID,
        day_of_week: str,
        start_time: time,
        end_time: time,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        existing = await self._class_schedule_repo.list_for_room_and_day(
            institution_id, room_id, day_of_week, exclude_id=exclude_id
        )
        for row in existing:
            if start_time < row.end_time and end_time > row.start_time:
                raise ConflictError(
                    "Room is already booked for an overlapping time slot on this day."
                )
