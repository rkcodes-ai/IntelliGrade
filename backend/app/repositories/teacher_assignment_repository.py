"""Persistence access for `TeacherAssignment`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.teacher_assignment import TeacherAssignment
from app.repositories.tenant_repository import TenantScopedRepository


class TeacherAssignmentRepository(TenantScopedRepository[TeacherAssignment]):
    search_fields: tuple[str, ...] = ()
    sortable_fields = ("assigned_from", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(TeacherAssignment, session)

    async def get_active_primary(
        self, subject_allocation_id: uuid.UUID, institution_id: uuid.UUID
    ) -> TeacherAssignment | None:
        """
        The current active row with `assignment_role == "primary"` for this
        allocation, or `None`. Used by `TeacherAssignmentService` to enforce
        the "at most one active primary teacher per subject allocation"
        business rule on both create and update.
        """
        query = select(TeacherAssignment).where(
            TeacherAssignment.institution_id == institution_id,
            TeacherAssignment.subject_allocation_id == subject_allocation_id,
            TeacherAssignment.assignment_role == "primary",
            TeacherAssignment.is_active.is_(True),
            TeacherAssignment.deleted_at.is_(None),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
