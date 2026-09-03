"""Exam management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError
from app.models.exam import Exam
from app.repositories.exam_repository import ExamRepository
from app.schemas.exam import ExamCreate, ExamUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class ExamService(TenantScopedService[Exam]):
    resource_type = "exam"

    def __init__(
        self,
        session: AsyncSession,
        repo: ExamRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session, repo or ExamRepository(session), audit_service=audit_service)

    async def create(
        self, institution_id: uuid.UUID, data: ExamCreate, *, created_by: uuid.UUID | None
    ) -> Exam:
        # Local imports: `AssessmentRepository` and `SectionRepository` are
        # owned by sibling agents in this same wave and may not exist on
        # disk yet when this module is first imported — kept local so this
        # file stays importable regardless of import order (same pattern as
        # `class_schedule_service.py`).
        from app.repositories.assessment_repository import AssessmentRepository
        from app.repositories.section_repository import SectionRepository

        assessment = await AssessmentRepository(self.session).get_by_id_for_institution(
            data.assessment_id, institution_id
        )
        if assessment is None:
            raise NotFoundError("Assessment not found.")

        section = await SectionRepository(self.session).get_by_id_for_institution(
            data.section_id, institution_id
        )
        if section is None:
            raise NotFoundError("Section not found.")

        exam = Exam(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        exam = await self.repo.add(exam)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, exam.id)
        return exam

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: ExamUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> Exam:
        from app.repositories.assessment_repository import AssessmentRepository
        from app.repositories.section_repository import SectionRepository

        exam = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "assessment_id" in updates:
            assessment = await AssessmentRepository(self.session).get_by_id_for_institution(
                updates["assessment_id"], institution_id
            )
            if assessment is None:
                raise NotFoundError("Assessment not found.")

        if "section_id" in updates:
            section = await SectionRepository(self.session).get_by_id_for_institution(
                updates["section_id"], institution_id
            )
            if section is None:
                raise NotFoundError("Section not found.")

        for field, value in updates.items():
            setattr(exam, field, value)
        exam.updated_by = updated_by
        if updates:
            exam.current_version += 1
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(exam)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, exam.id)
        return exam
