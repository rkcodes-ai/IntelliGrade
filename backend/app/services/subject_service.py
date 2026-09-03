"""Subject management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.subject import Subject
from app.repositories.course_repository import CourseRepository
from app.repositories.subject_category_repository import SubjectCategoryRepository
from app.repositories.subject_repository import SubjectRepository
from app.schemas.subject import SubjectCreate, SubjectUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class SubjectService(TenantScopedService[Subject]):
    resource_type = "subject"

    def __init__(
        self,
        session: AsyncSession,
        repo: SubjectRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session, repo or SubjectRepository(session), audit_service=audit_service)

    async def create(
        self, institution_id: uuid.UUID, data: SubjectCreate, *, created_by: uuid.UUID | None
    ) -> Subject:
        course = await CourseRepository(self.session).get_by_id_for_institution(
            data.course_id, institution_id
        )
        if course is None:
            raise NotFoundError("Course not found.")

        subject_category = await SubjectCategoryRepository(self.session).get_by_id_for_institution(
            data.subject_category_id, institution_id
        )
        if subject_category is None:
            raise NotFoundError("Subject category not found.")

        if await self.repo.code_exists(institution_id, "code", data.code):
            raise ConflictError("A subject with that code already exists for this institution.")

        subject = Subject(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        subject = await self.repo.add(subject)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, subject.id)
        return subject

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: SubjectUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> Subject:
        subject = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "course_id" in updates:
            course = await CourseRepository(self.session).get_by_id_for_institution(
                updates["course_id"], institution_id
            )
            if course is None:
                raise NotFoundError("Course not found.")

        if "subject_category_id" in updates:
            subject_category = await SubjectCategoryRepository(
                self.session
            ).get_by_id_for_institution(updates["subject_category_id"], institution_id)
            if subject_category is None:
                raise NotFoundError("Subject category not found.")

        if "code" in updates and await self.repo.code_exists(
            institution_id, "code", updates["code"], exclude_id=entity_id
        ):
            raise ConflictError("A subject with that code already exists for this institution.")

        for field, value in updates.items():
            setattr(subject, field, value)
        subject.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(subject)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, subject.id)
        return subject
