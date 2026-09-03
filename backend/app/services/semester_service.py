"""
Semester management service.

Business rules enforced here (not in the database): `start_date` must
precede `end_date`, the semester's date range must fall within its parent
academic year's date range, `semester_number` must be unique per academic
year, and no two semesters within the same academic year may have
overlapping date ranges.
"""

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.academic_year import AcademicYear
from app.models.semester import Semester
from app.repositories.academic_year_repository import AcademicYearRepository
from app.repositories.semester_repository import SemesterRepository
from app.schemas.semester import SemesterCreate, SemesterUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class SemesterService(TenantScopedService[Semester]):
    resource_type = "semester"

    def __init__(
        self,
        session: AsyncSession,
        repo: SemesterRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        repo = repo or SemesterRepository(session)
        super().__init__(session, repo, audit_service=audit_service)
        # `TenantScopedService.repo` is typed as the generic
        # `TenantScopedRepository[Semester]` base, which doesn't expose
        # `list_by_academic_year` (a `SemesterRepository`-specific method) —
        # keep a narrowly-typed reference for the sibling-overlap check.
        self._semester_repo = repo

    async def _get_academic_year(
        self, institution_id: uuid.UUID, academic_year_id: uuid.UUID
    ) -> AcademicYear:
        academic_year = await AcademicYearRepository(self.session).get_by_id_for_institution(
            academic_year_id, institution_id
        )
        if academic_year is None:
            raise NotFoundError("Academic year not found.")
        return academic_year

    async def _assert_no_sibling_overlap(
        self,
        institution_id: uuid.UUID,
        academic_year_id: uuid.UUID,
        start_date: date,
        end_date: date,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        existing_semesters = await self._semester_repo.list_by_academic_year(
            academic_year_id, institution_id
        )
        for existing in existing_semesters:
            if exclude_id is not None and existing.id == exclude_id:
                continue
            if start_date <= existing.end_date and end_date >= existing.start_date:
                raise ConflictError(
                    f"Semester dates overlap with existing semester '{existing.name}'."
                )

    async def create(
        self, institution_id: uuid.UUID, data: SemesterCreate, *, created_by: uuid.UUID | None
    ) -> Semester:
        academic_year = await self._get_academic_year(institution_id, data.academic_year_id)

        if data.start_date >= data.end_date:
            raise ValidationAppError("start_date must be before end_date.")

        if data.start_date < academic_year.start_date or data.end_date > academic_year.end_date:
            raise ValidationAppError(
                "Semester dates must fall within the academic year's date range."
            )

        if await self.repo.code_exists(
            institution_id,
            "semester_number",
            data.semester_number,  # type: ignore[arg-type] # code_exists's code_value
            # is typed `str` but does a plain `==` comparison, so it works for any
            # column type — see TenantScopedRepository.code_exists docstring.
            scope_conditions=(Semester.academic_year_id == data.academic_year_id,),
        ):
            raise ConflictError(
                "A semester with that semester_number already exists for this academic year."
            )

        await self._assert_no_sibling_overlap(
            institution_id, data.academic_year_id, data.start_date, data.end_date
        )

        semester = Semester(
            institution_id=institution_id, **data.model_dump(), created_by=created_by
        )
        semester = await self.repo.add(semester)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, semester.id)
        return semester

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: SemesterUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> Semester:
        semester = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        target_academic_year_id = updates.get("academic_year_id", semester.academic_year_id)
        target_start_date = updates.get("start_date", semester.start_date)
        target_end_date = updates.get("end_date", semester.end_date)
        target_semester_number = updates.get("semester_number", semester.semester_number)

        dates_or_parent_changed = (
            "academic_year_id" in updates or "start_date" in updates or "end_date" in updates
        )

        if dates_or_parent_changed:
            academic_year = await self._get_academic_year(institution_id, target_academic_year_id)
            if target_start_date >= target_end_date:
                raise ValidationAppError("start_date must be before end_date.")
            if (
                target_start_date < academic_year.start_date
                or target_end_date > academic_year.end_date
            ):
                raise ValidationAppError(
                    "Semester dates must fall within the academic year's date range."
                )

        if (
            "semester_number" in updates or "academic_year_id" in updates
        ) and await self.repo.code_exists(
            institution_id,
            "semester_number",
            target_semester_number,
            exclude_id=entity_id,
            scope_conditions=(Semester.academic_year_id == target_academic_year_id,),
        ):
            raise ConflictError(
                "A semester with that semester_number already exists for this academic year."
            )

        if dates_or_parent_changed:
            await self._assert_no_sibling_overlap(
                institution_id,
                target_academic_year_id,
                target_start_date,
                target_end_date,
                exclude_id=entity_id,
            )

        for field, value in updates.items():
            setattr(semester, field, value)
        semester.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(semester)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, semester.id)
        return semester
