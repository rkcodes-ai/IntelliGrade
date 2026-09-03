"""AcademicCalendarEvent management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.academic_calendar_event import AcademicCalendarEvent
from app.repositories.academic_calendar_event_repository import AcademicCalendarEventRepository
from app.repositories.academic_year_repository import AcademicYearRepository
from app.schemas.academic_calendar_event import (
    AcademicCalendarEventCreate,
    AcademicCalendarEventUpdate,
)
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class AcademicCalendarEventService(TenantScopedService[AcademicCalendarEvent]):
    resource_type = "academic_calendar_event"

    def __init__(
        self,
        session: AsyncSession,
        repo: AcademicCalendarEventRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or AcademicCalendarEventRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: AcademicCalendarEventCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> AcademicCalendarEvent:
        academic_year = await AcademicYearRepository(self.session).get_by_id_for_institution(
            data.academic_year_id, institution_id
        )
        if academic_year is None:
            raise NotFoundError("Academic year not found.")

        if data.start_date > data.end_date:
            raise ValidationAppError("start_date must not be after end_date.")

        event = AcademicCalendarEvent(
            institution_id=institution_id,
            **data.model_dump(),
            created_by=created_by,
        )
        event = await self.repo.add(event)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, event.id)
        return event

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: AcademicCalendarEventUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> AcademicCalendarEvent:
        event = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "academic_year_id" in updates:
            academic_year = await AcademicYearRepository(self.session).get_by_id_for_institution(
                updates["academic_year_id"], institution_id
            )
            if academic_year is None:
                raise NotFoundError("Academic year not found.")

        target_start_date = updates.get("start_date", event.start_date)
        target_end_date = updates.get("end_date", event.end_date)
        if (
            "start_date" in updates or "end_date" in updates
        ) and target_start_date > target_end_date:
            raise ValidationAppError("start_date must not be after end_date.")

        for field, value in updates.items():
            setattr(event, field, value)
        event.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(event)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, event.id)
        return event
