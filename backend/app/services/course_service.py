"""Course management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.course import Course
from app.repositories.course_repository import CourseRepository
from app.schemas.course import CourseCreate, CourseUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class CourseService(TenantScopedService[Course]):
    resource_type = "course"

    def __init__(
        self,
        session: AsyncSession,
        repo: CourseRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session, repo or CourseRepository(session), audit_service=audit_service)

    async def create(
        self, institution_id: uuid.UUID, data: CourseCreate, *, created_by: uuid.UUID | None
    ) -> Course:
        # Import kept local to the method (not module-level) so this file
        # does not need to exist on disk until create() actually runs —
        # Program is owned by a sibling agent working in the same wave.
        from app.repositories.program_repository import ProgramRepository

        program = await ProgramRepository(self.session).get_by_id_for_institution(
            data.program_id, institution_id
        )
        if program is None:
            raise NotFoundError("Program not found.")

        if await self.repo.code_exists(
            institution_id,
            "code",
            data.code,
            scope_conditions=(Course.program_id == data.program_id,),
        ):
            raise ConflictError("A course with that code already exists for this program.")

        course = Course(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        course = await self.repo.add(course)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, course.id)
        return course

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: CourseUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> Course:
        from app.repositories.program_repository import ProgramRepository

        course = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        target_program_id = updates.get("program_id", course.program_id)

        if "program_id" in updates:
            program = await ProgramRepository(self.session).get_by_id_for_institution(
                updates["program_id"], institution_id
            )
            if program is None:
                raise NotFoundError("Program not found.")

        if "code" in updates or "program_id" in updates:
            code_value = updates.get("code", course.code)
            if await self.repo.code_exists(
                institution_id,
                "code",
                code_value,
                exclude_id=entity_id,
                scope_conditions=(Course.program_id == target_program_id,),
            ):
                raise ConflictError("A course with that code already exists for this program.")

        for field, value in updates.items():
            setattr(course, field, value)
        course.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(course)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, course.id)
        return course
