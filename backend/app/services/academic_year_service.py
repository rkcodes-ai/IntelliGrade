"""
AcademicYear management service.

Business rules enforced here (not in the database): `start_date` must
precede `end_date`, `year_label` must be unique per institution, and no two
academic years for the same institution may have overlapping date ranges —
the "academic year overlaps" validation called out in the module spec.
"""

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, ValidationAppError
from app.models.academic_year import AcademicYear
from app.repositories.academic_year_repository import AcademicYearRepository
from app.schemas.academic_year import AcademicYearCreate, AcademicYearUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class AcademicYearService(TenantScopedService[AcademicYear]):
    resource_type = "academic_year"

    def __init__(
        self,
        session: AsyncSession,
        repo: AcademicYearRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        repo = repo or AcademicYearRepository(session)
        super().__init__(session, repo, audit_service=audit_service)
        # `TenantScopedService.repo` is typed as the generic
        # `TenantScopedRepository[AcademicYear]` base, which doesn't expose
        # `list_all_for_institution` (an `AcademicYearRepository`-specific
        # method) — keep a narrowly-typed reference for the overlap check.
        self._academic_year_repo = repo

    async def _assert_no_overlap(
        self,
        institution_id: uuid.UUID,
        start_date: date,
        end_date: date,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        existing_years = await self._academic_year_repo.list_all_for_institution(institution_id)
        for existing in existing_years:
            if exclude_id is not None and existing.id == exclude_id:
                continue
            if start_date <= existing.end_date and end_date >= existing.start_date:
                raise ConflictError(
                    f"Academic year dates overlap with existing academic year "
                    f"'{existing.year_label}'."
                )

    async def create(
        self, institution_id: uuid.UUID, data: AcademicYearCreate, *, created_by: uuid.UUID | None
    ) -> AcademicYear:
        if data.start_date >= data.end_date:
            raise ValidationAppError("start_date must be before end_date.")

        if await self.repo.code_exists(institution_id, "year_label", data.year_label):
            raise ConflictError("An academic year with that label already exists.")

        await self._assert_no_overlap(institution_id, data.start_date, data.end_date)

        academic_year = AcademicYear(
            institution_id=institution_id, **data.model_dump(), created_by=created_by
        )
        academic_year = await self.repo.add(academic_year)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, academic_year.id)
        return academic_year

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: AcademicYearUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> AcademicYear:
        academic_year = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        target_start_date = updates.get("start_date", academic_year.start_date)
        target_end_date = updates.get("end_date", academic_year.end_date)

        if "start_date" in updates or "end_date" in updates:
            if target_start_date >= target_end_date:
                raise ValidationAppError("start_date must be before end_date.")
            await self._assert_no_overlap(
                institution_id, target_start_date, target_end_date, exclude_id=entity_id
            )

        if "year_label" in updates and await self.repo.code_exists(
            institution_id, "year_label", updates["year_label"], exclude_id=entity_id
        ):
            raise ConflictError("An academic year with that label already exists.")

        for field, value in updates.items():
            setattr(academic_year, field, value)
        academic_year.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(academic_year)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, academic_year.id)
        return academic_year
