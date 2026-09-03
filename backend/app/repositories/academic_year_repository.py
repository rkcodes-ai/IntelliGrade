"""Persistence access for `AcademicYear`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic_year import AcademicYear
from app.repositories.tenant_repository import TenantScopedRepository


class AcademicYearRepository(TenantScopedRepository[AcademicYear]):
    search_fields = ("year_label",)
    sortable_fields = ("year_label", "start_date", "end_date", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AcademicYear, session)

    async def list_all_for_institution(self, institution_id: uuid.UUID) -> list[AcademicYear]:
        """
        Every non-deleted academic year for an institution, unpaginated,
        ordered by `start_date` — used by `AcademicYearService` to run the
        overlap-check business rule against the full set of existing years.
        """
        query = (
            select(AcademicYear)
            .where(
                AcademicYear.institution_id == institution_id,
                AcademicYear.deleted_at.is_(None),
            )
            .order_by(AcademicYear.start_date)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
