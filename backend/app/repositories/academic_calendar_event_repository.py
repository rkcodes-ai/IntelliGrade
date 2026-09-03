"""Persistence access for `AcademicCalendarEvent`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic_calendar_event import AcademicCalendarEvent
from app.repositories.tenant_repository import TenantScopedRepository


class AcademicCalendarEventRepository(TenantScopedRepository[AcademicCalendarEvent]):
    search_fields = ("title",)
    sortable_fields = ("title", "start_date", "end_date", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AcademicCalendarEvent, session)
