"""Persistence access for `StudentEnrollment`."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student_enrollment import StudentEnrollment
from app.repositories.tenant_repository import TenantScopedRepository


class StudentEnrollmentRepository(TenantScopedRepository[StudentEnrollment]):
    search_fields = ("roll_number",)
    sortable_fields = ("roll_number", "enrollment_date", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(StudentEnrollment, session)

    async def count_active_in_section(self, section_id: uuid.UUID) -> int:
        """Number of active, non-deleted enrollments in a section — used to enforce capacity."""
        subquery = (
            select(StudentEnrollment.id)
            .where(
                StudentEnrollment.section_id == section_id,
                StudentEnrollment.is_active.is_(True),
                StudentEnrollment.deleted_at.is_(None),
            )
            .subquery()
        )
        result = await self.session.execute(select(func.count()).select_from(subquery))
        return result.scalar_one()
