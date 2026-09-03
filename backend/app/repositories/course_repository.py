"""Persistence access for `Course`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.repositories.tenant_repository import TenantScopedRepository


class CourseRepository(TenantScopedRepository[Course]):
    search_fields = ("name", "code")
    sortable_fields = ("name", "code", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Course, session)
