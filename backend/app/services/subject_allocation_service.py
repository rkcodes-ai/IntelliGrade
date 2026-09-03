"""SubjectAllocation management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.subject_allocation import SubjectAllocation
from app.repositories.academic_year_repository import AcademicYearRepository
from app.repositories.room_repository import RoomRepository
from app.repositories.subject_allocation_repository import SubjectAllocationRepository
from app.repositories.subject_repository import SubjectRepository
from app.repositories.user_repository import UserRepository
from app.schemas.subject_allocation import SubjectAllocationCreate, SubjectAllocationUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class SubjectAllocationService(TenantScopedService[SubjectAllocation]):
    resource_type = "subject_allocation"

    def __init__(
        self,
        session: AsyncSession,
        repo: SubjectAllocationRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or SubjectAllocationRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: SubjectAllocationCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> SubjectAllocation:
        # Imports for Section/Semester kept local to the method (not
        # module-level) so this file does not need those tables to exist on
        # disk until create() actually runs — Section and Semester are owned
        # by a parallel sibling agent working in this same wave.
        from app.repositories.section_repository import SectionRepository
        from app.repositories.semester_repository import SemesterRepository

        subject = await SubjectRepository(self.session).get_by_id_for_institution(
            data.subject_id, institution_id
        )
        if subject is None:
            raise NotFoundError("Subject not found.")

        section = await SectionRepository(self.session).get_by_id_for_institution(
            data.section_id, institution_id
        )
        if section is None:
            raise NotFoundError("Section not found.")

        semester = await SemesterRepository(self.session).get_by_id_for_institution(
            data.semester_id, institution_id
        )
        if semester is None:
            raise NotFoundError("Semester not found.")

        academic_year = await AcademicYearRepository(self.session).get_by_id_for_institution(
            data.academic_year_id, institution_id
        )
        if academic_year is None:
            raise NotFoundError("Academic year not found.")

        teacher = await UserRepository(self.session).get_by_id(data.teacher_user_id)
        if teacher is None:
            raise NotFoundError("Teacher not found.")

        if data.room_id is not None:
            room = await RoomRepository(self.session).get_by_id_for_institution(
                data.room_id, institution_id
            )
            if room is None:
                raise NotFoundError("Room not found.")

        if await self.repo.code_exists(
            institution_id,
            "subject_id",
            data.subject_id,  # type: ignore[arg-type]
            scope_conditions=(
                SubjectAllocation.section_id == data.section_id,
                SubjectAllocation.semester_id == data.semester_id,
            ),
        ):
            raise ConflictError(
                "This subject is already allocated to this section for this semester."
            )

        allocation = SubjectAllocation(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        allocation = await self.repo.add(allocation)
        await self._log_audit(AuditAction.ACADEMIC_ASSIGNMENT_CREATED, created_by, allocation.id)
        return allocation

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: SubjectAllocationUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> SubjectAllocation:
        from app.repositories.section_repository import SectionRepository
        from app.repositories.semester_repository import SemesterRepository

        allocation = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "subject_id" in updates:
            subject = await SubjectRepository(self.session).get_by_id_for_institution(
                updates["subject_id"], institution_id
            )
            if subject is None:
                raise NotFoundError("Subject not found.")

        if "section_id" in updates:
            section = await SectionRepository(self.session).get_by_id_for_institution(
                updates["section_id"], institution_id
            )
            if section is None:
                raise NotFoundError("Section not found.")

        if "semester_id" in updates:
            semester = await SemesterRepository(self.session).get_by_id_for_institution(
                updates["semester_id"], institution_id
            )
            if semester is None:
                raise NotFoundError("Semester not found.")

        if "academic_year_id" in updates:
            academic_year = await AcademicYearRepository(self.session).get_by_id_for_institution(
                updates["academic_year_id"], institution_id
            )
            if academic_year is None:
                raise NotFoundError("Academic year not found.")

        if "teacher_user_id" in updates:
            teacher = await UserRepository(self.session).get_by_id(updates["teacher_user_id"])
            if teacher is None:
                raise NotFoundError("Teacher not found.")

        if "room_id" in updates and updates["room_id"] is not None:
            room = await RoomRepository(self.session).get_by_id_for_institution(
                updates["room_id"], institution_id
            )
            if room is None:
                raise NotFoundError("Room not found.")

        if {"subject_id", "section_id", "semester_id"} & updates.keys():
            target_subject_id = updates.get("subject_id", allocation.subject_id)
            target_section_id = updates.get("section_id", allocation.section_id)
            target_semester_id = updates.get("semester_id", allocation.semester_id)
            if await self.repo.code_exists(
                institution_id,
                "subject_id",
                target_subject_id,
                exclude_id=entity_id,
                scope_conditions=(
                    SubjectAllocation.section_id == target_section_id,
                    SubjectAllocation.semester_id == target_semester_id,
                ),
            ):
                raise ConflictError(
                    "This subject is already allocated to this section for this semester."
                )

        for field, value in updates.items():
            setattr(allocation, field, value)
        allocation.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(allocation)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, allocation.id)
        return allocation
