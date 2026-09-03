"""ExamSchedule management service."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.exam_schedule import ExamSchedule
from app.repositories.exam_schedule_repository import ExamScheduleRepository
from app.schemas.exam_schedule import ExamScheduleCreate, ExamScheduleUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class ExamScheduleService(TenantScopedService[ExamSchedule]):
    resource_type = "exam_schedule"

    def __init__(
        self,
        session: AsyncSession,
        repo: ExamScheduleRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        repo = repo or ExamScheduleRepository(session)
        super().__init__(session, repo, audit_service=audit_service)
        self._exam_schedule_repo = repo

    async def create(
        self,
        institution_id: uuid.UUID,
        data: ExamScheduleCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> ExamSchedule:
        # Local import: `ExamRepository` is a same-wave sibling and may not
        # exist on disk yet when this module is first imported — kept local
        # so this file stays importable regardless of import order (same
        # pattern as `class_schedule_service.py`).
        from app.repositories.exam_repository import ExamRepository

        exam = await ExamRepository(self.session).get_by_id_for_institution(
            data.exam_id, institution_id
        )
        if exam is None:
            raise NotFoundError("Exam not found.")

        if data.start_time >= data.end_time:
            raise ValidationAppError("start_time must be before end_time.")

        if data.room_id is not None:
            await self._assert_no_overlap(
                institution_id, data.room_id, data.start_time, data.end_time
            )

        schedule = ExamSchedule(
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
        data: ExamScheduleUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> ExamSchedule:
        from app.repositories.exam_repository import ExamRepository

        schedule = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "exam_id" in updates:
            exam = await ExamRepository(self.session).get_by_id_for_institution(
                updates["exam_id"], institution_id
            )
            if exam is None:
                raise NotFoundError("Exam not found.")

        target_room_id = updates.get("room_id", schedule.room_id)
        target_start = updates.get("start_time", schedule.start_time)
        target_end = updates.get("end_time", schedule.end_time)

        if target_start >= target_end:
            raise ValidationAppError("start_time must be before end_time.")

        if target_room_id is not None and any(
            f in updates for f in ("room_id", "start_time", "end_time")
        ):
            await self._assert_no_overlap(
                institution_id,
                target_room_id,
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

        await self._log_audit(AuditAction.EXAM_SCHEDULE_UPDATED, updated_by, schedule.id)
        return schedule

    async def _assert_no_overlap(
        self,
        institution_id: uuid.UUID,
        room_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        existing = await self._exam_schedule_repo.list_for_room_in_range(
            institution_id, room_id, start_time, end_time, exclude_id=exclude_id
        )
        if existing:
            raise ConflictError("This room is already booked for an overlapping time range.")
