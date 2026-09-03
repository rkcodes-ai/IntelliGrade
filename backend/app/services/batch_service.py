"""
Batch management service.

Business rules enforced here (not in the database): `course_id` must exist
for the institution, `start_year` must precede `end_year`, and `name` must
be unique per course.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.batch import Batch
from app.repositories.batch_repository import BatchRepository
from app.repositories.course_repository import CourseRepository
from app.schemas.batch import BatchCreate, BatchUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class BatchService(TenantScopedService[Batch]):
    resource_type = "batch"

    def __init__(
        self,
        session: AsyncSession,
        repo: BatchRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session, repo or BatchRepository(session), audit_service=audit_service)

    async def _assert_course_exists(self, institution_id: uuid.UUID, course_id: uuid.UUID) -> None:
        course = await CourseRepository(self.session).get_by_id_for_institution(
            course_id, institution_id
        )
        if course is None:
            raise NotFoundError("Course not found.")

    async def create(
        self, institution_id: uuid.UUID, data: BatchCreate, *, created_by: uuid.UUID | None
    ) -> Batch:
        await self._assert_course_exists(institution_id, data.course_id)

        if data.start_year >= data.end_year:
            raise ValidationAppError("start_year must be before end_year.")

        if await self.repo.code_exists(
            institution_id,
            "name",
            data.name,
            scope_conditions=(Batch.course_id == data.course_id,),
        ):
            raise ConflictError("A batch with that name already exists for this course.")

        batch = Batch(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        batch = await self.repo.add(batch)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, batch.id)
        return batch

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: BatchUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> Batch:
        batch = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        target_course_id = updates.get("course_id", batch.course_id)
        target_start_year = updates.get("start_year", batch.start_year)
        target_end_year = updates.get("end_year", batch.end_year)

        if "course_id" in updates:
            await self._assert_course_exists(institution_id, target_course_id)

        if (
            "start_year" in updates or "end_year" in updates
        ) and target_start_year >= target_end_year:
            raise ValidationAppError("start_year must be before end_year.")

        if "name" in updates or "course_id" in updates:
            name_value = updates.get("name", batch.name)
            if await self.repo.code_exists(
                institution_id,
                "name",
                name_value,
                exclude_id=entity_id,
                scope_conditions=(Batch.course_id == target_course_id,),
            ):
                raise ConflictError("A batch with that name already exists for this course.")

        for field, value in updates.items():
            setattr(batch, field, value)
        batch.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(batch)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, batch.id)
        return batch
