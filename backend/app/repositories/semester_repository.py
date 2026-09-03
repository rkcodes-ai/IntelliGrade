"""Persistence access for `Semester`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.semester import Semester
from app.repositories.tenant_repository import TenantScopedRepository


class SemesterRepository(TenantScopedRepository[Semester]):
    search_fields = ("name",)
    sortable_fields = (
        "name",
        "semester_number",
        "start_date",
        "end_date",
        "created_at",
        "updated_at",
    )

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Semester, session)

    async def list_by_academic_year(
        self, academic_year_id: uuid.UUID, institution_id: uuid.UUID
    ) -> list[Semester]:
        """
        Every non-deleted semester for an academic year, unpaginated — used
        by `SemesterService` to run the sibling-overlap business rule
        against the full set of existing semesters in the same academic
        year.
        """
        query = select(Semester).where(
            Semester.institution_id == institution_id,
            Semester.academic_year_id == academic_year_id,
            Semester.deleted_at.is_(None),
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
