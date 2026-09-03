"""TeacherAssignment management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.teacher_assignment import TeacherAssignment
from app.repositories.teacher_assignment_repository import TeacherAssignmentRepository
from app.repositories.user_repository import UserRepository
from app.schemas.teacher_assignment import TeacherAssignmentCreate, TeacherAssignmentUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class TeacherAssignmentService(TenantScopedService[TeacherAssignment]):
    resource_type = "teacher_assignment"

    def __init__(
        self,
        session: AsyncSession,
        repo: TeacherAssignmentRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        repo = repo or TeacherAssignmentRepository(session)
        super().__init__(session, repo, audit_service=audit_service)
        self._teacher_assignment_repo = repo

    async def create(
        self,
        institution_id: uuid.UUID,
        data: TeacherAssignmentCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> TeacherAssignment:
        # Local import: SubjectAllocation is owned by a sibling agent in
        # this same wave and may not exist on disk yet when this module is
        # first imported — kept local so this file stays importable
        # regardless of import order.
        from app.repositories.subject_allocation_repository import SubjectAllocationRepository

        allocation = await SubjectAllocationRepository(self.session).get_by_id_for_institution(
            data.subject_allocation_id, institution_id
        )
        if allocation is None:
            raise NotFoundError("Subject allocation not found.")

        teacher = await UserRepository(self.session).get_by_id(data.teacher_user_id)
        if teacher is None:
            raise NotFoundError("Teacher not found.")

        if await self.repo.code_exists(
            institution_id,
            "teacher_user_id",
            data.teacher_user_id,  # type: ignore[arg-type]
            scope_conditions=(
                TeacherAssignment.subject_allocation_id == data.subject_allocation_id,
            ),
        ):
            raise ConflictError("This teacher is already assigned to this subject allocation.")

        if data.assignment_role == "primary":
            existing_primary = await self._teacher_assignment_repo.get_active_primary(
                data.subject_allocation_id, institution_id
            )
            if existing_primary is not None:
                raise ConflictError(
                    "This subject allocation already has an active primary teacher."
                )

        assignment = TeacherAssignment(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        assignment = await self.repo.add(assignment)
        await self._log_audit(AuditAction.ACADEMIC_ASSIGNMENT_CREATED, created_by, assignment.id)
        return assignment

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: TeacherAssignmentUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> TeacherAssignment:
        from app.repositories.subject_allocation_repository import SubjectAllocationRepository

        assignment = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "subject_allocation_id" in updates:
            allocation = await SubjectAllocationRepository(self.session).get_by_id_for_institution(
                updates["subject_allocation_id"], institution_id
            )
            if allocation is None:
                raise NotFoundError("Subject allocation not found.")

        if "teacher_user_id" in updates:
            teacher = await UserRepository(self.session).get_by_id(updates["teacher_user_id"])
            if teacher is None:
                raise NotFoundError("Teacher not found.")

        target_allocation_id = updates.get(
            "subject_allocation_id", assignment.subject_allocation_id
        )
        target_teacher_id = updates.get("teacher_user_id", assignment.teacher_user_id)

        if (
            "subject_allocation_id" in updates or "teacher_user_id" in updates
        ) and await self.repo.code_exists(
            institution_id,
            "teacher_user_id",
            target_teacher_id,
            exclude_id=entity_id,
            scope_conditions=(TeacherAssignment.subject_allocation_id == target_allocation_id,),
        ):
            raise ConflictError("This teacher is already assigned to this subject allocation.")

        target_role = updates.get("assignment_role", assignment.assignment_role)
        # Re-run the active-primary conflict check whenever the effective
        # role is (or becomes) "primary" and either the role or the
        # allocation is changing — covers both "promoted to primary" and
        # "moved to an allocation that already has an active primary".
        if target_role == "primary" and (
            "assignment_role" in updates or "subject_allocation_id" in updates
        ):
            existing_primary = await self._teacher_assignment_repo.get_active_primary(
                target_allocation_id, institution_id
            )
            if existing_primary is not None and existing_primary.id != entity_id:
                raise ConflictError(
                    "This subject allocation already has an active primary teacher."
                )

        for field, value in updates.items():
            setattr(assignment, field, value)
        assignment.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(assignment)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, assignment.id)
        return assignment
