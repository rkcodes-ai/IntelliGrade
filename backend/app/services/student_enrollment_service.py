"""StudentEnrollment management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.student_enrollment import StudentEnrollment
from app.repositories.academic_status_repository import AcademicStatusRepository
from app.repositories.academic_year_repository import AcademicYearRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.student_enrollment_repository import StudentEnrollmentRepository
from app.repositories.user_repository import UserRepository
from app.schemas.student_enrollment import StudentEnrollmentCreate, StudentEnrollmentUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class StudentEnrollmentService(TenantScopedService[StudentEnrollment]):
    resource_type = "student_enrollment"

    def __init__(
        self,
        session: AsyncSession,
        repo: StudentEnrollmentRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        repo = repo or StudentEnrollmentRepository(session)
        super().__init__(session, repo, audit_service=audit_service)
        self._student_enrollment_repo = repo

    async def create(
        self,
        institution_id: uuid.UUID,
        data: StudentEnrollmentCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> StudentEnrollment:
        # Local imports: Batch/Section/Semester are owned by a sibling agent
        # in this same wave and may not exist on disk yet when this module
        # is first imported — kept local so this file stays importable
        # regardless of import order.
        from app.repositories.batch_repository import BatchRepository
        from app.repositories.section_repository import SectionRepository
        from app.repositories.semester_repository import SemesterRepository

        student = await UserRepository(self.session).get_by_id(data.student_user_id)
        if student is None:
            raise NotFoundError("Student not found.")

        batch = await BatchRepository(self.session).get_by_id_for_institution(
            data.batch_id, institution_id
        )
        if batch is None:
            raise NotFoundError("Batch not found.")

        section = await SectionRepository(self.session).get_by_id_for_institution(
            data.section_id, institution_id
        )
        if section is None:
            raise NotFoundError("Section not found.")

        course = await CourseRepository(self.session).get_by_id_for_institution(
            data.course_id, institution_id
        )
        if course is None:
            raise NotFoundError("Course not found.")

        academic_year = await AcademicYearRepository(self.session).get_by_id_for_institution(
            data.academic_year_id, institution_id
        )
        if academic_year is None:
            raise NotFoundError("Academic year not found.")

        semester = await SemesterRepository(self.session).get_by_id_for_institution(
            data.semester_id, institution_id
        )
        if semester is None:
            raise NotFoundError("Semester not found.")

        academic_status = await AcademicStatusRepository(self.session).get_by_id_for_institution(
            data.academic_status_id, institution_id
        )
        if academic_status is None:
            raise NotFoundError("Academic status not found.")

        if await self.repo.code_exists(
            institution_id,
            "student_user_id",
            data.student_user_id,  # type: ignore[arg-type]
            scope_conditions=(
                StudentEnrollment.academic_year_id == data.academic_year_id,
                StudentEnrollment.semester_id == data.semester_id,
            ),
        ):
            raise ConflictError(
                "This student is already enrolled for this academic year and semester."
            )

        if await self.repo.code_exists(
            institution_id,
            "roll_number",
            data.roll_number,
            scope_conditions=(StudentEnrollment.section_id == data.section_id,),
        ):
            raise ConflictError("This roll number is already used in this section.")

        current_count = await self._student_enrollment_repo.count_active_in_section(data.section_id)
        if current_count >= section.max_capacity:
            raise ConflictError("This section has reached its maximum capacity.")

        enrollment = StudentEnrollment(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        enrollment = await self.repo.add(enrollment)
        await self._log_audit(AuditAction.ACADEMIC_ENROLLMENT_CREATED, created_by, enrollment.id)
        return enrollment

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: StudentEnrollmentUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> StudentEnrollment:
        from app.repositories.batch_repository import BatchRepository
        from app.repositories.section_repository import SectionRepository
        from app.repositories.semester_repository import SemesterRepository

        enrollment = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "student_user_id" in updates:
            student = await UserRepository(self.session).get_by_id(updates["student_user_id"])
            if student is None:
                raise NotFoundError("Student not found.")

        if "batch_id" in updates:
            batch = await BatchRepository(self.session).get_by_id_for_institution(
                updates["batch_id"], institution_id
            )
            if batch is None:
                raise NotFoundError("Batch not found.")

        target_section = None
        if "section_id" in updates:
            target_section = await SectionRepository(self.session).get_by_id_for_institution(
                updates["section_id"], institution_id
            )
            if target_section is None:
                raise NotFoundError("Section not found.")

        if "course_id" in updates:
            course = await CourseRepository(self.session).get_by_id_for_institution(
                updates["course_id"], institution_id
            )
            if course is None:
                raise NotFoundError("Course not found.")

        if "academic_year_id" in updates:
            academic_year = await AcademicYearRepository(self.session).get_by_id_for_institution(
                updates["academic_year_id"], institution_id
            )
            if academic_year is None:
                raise NotFoundError("Academic year not found.")

        if "semester_id" in updates:
            semester = await SemesterRepository(self.session).get_by_id_for_institution(
                updates["semester_id"], institution_id
            )
            if semester is None:
                raise NotFoundError("Semester not found.")

        if "academic_status_id" in updates:
            academic_status = await AcademicStatusRepository(
                self.session
            ).get_by_id_for_institution(updates["academic_status_id"], institution_id)
            if academic_status is None:
                raise NotFoundError("Academic status not found.")

        target_year_id = updates.get("academic_year_id", enrollment.academic_year_id)
        target_semester_id = updates.get("semester_id", enrollment.semester_id)
        target_student_id = updates.get("student_user_id", enrollment.student_user_id)

        if any(
            f in updates for f in ("student_user_id", "academic_year_id", "semester_id")
        ) and await self.repo.code_exists(
            institution_id,
            "student_user_id",
            target_student_id,
            exclude_id=entity_id,
            scope_conditions=(
                StudentEnrollment.academic_year_id == target_year_id,
                StudentEnrollment.semester_id == target_semester_id,
            ),
        ):
            raise ConflictError(
                "This student is already enrolled for this academic year and semester."
            )

        target_section_id = updates.get("section_id", enrollment.section_id)
        target_roll_number = updates.get("roll_number", enrollment.roll_number)

        if ("section_id" in updates or "roll_number" in updates) and await self.repo.code_exists(
            institution_id,
            "roll_number",
            target_roll_number,
            exclude_id=entity_id,
            scope_conditions=(StudentEnrollment.section_id == target_section_id,),
        ):
            raise ConflictError("This roll number is already used in this section.")

        if target_section is not None:
            current_count = await self._student_enrollment_repo.count_active_in_section(
                target_section_id
            )
            if current_count >= target_section.max_capacity:
                raise ConflictError("This section has reached its maximum capacity.")

        for field, value in updates.items():
            setattr(enrollment, field, value)
        enrollment.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(enrollment)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, enrollment.id)
        return enrollment

    async def change_status(
        self,
        institution_id: uuid.UUID,
        enrollment_id: uuid.UUID,
        new_status_id: uuid.UUID,
        *,
        actor_id: uuid.UUID | None,
    ) -> StudentEnrollment:
        """Dedicated status-transition endpoint, audited distinctly from a generic update."""
        enrollment = await self.get_by_id(institution_id, enrollment_id)

        academic_status = await AcademicStatusRepository(self.session).get_by_id_for_institution(
            new_status_id, institution_id
        )
        if academic_status is None:
            raise NotFoundError("Academic status not found.")

        enrollment.academic_status_id = new_status_id
        enrollment.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(enrollment)

        await self._log_audit(AuditAction.ACADEMIC_STATUS_CHANGED, actor_id, enrollment.id)
        return enrollment
