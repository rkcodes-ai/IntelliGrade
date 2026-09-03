"""Assessment management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError
from app.models.assessment import Assessment
from app.repositories.assessment_repository import AssessmentRepository
from app.schemas.assessment import AssessmentCreate, AssessmentUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class AssessmentService(TenantScopedService[Assessment]):
    resource_type = "assessment"

    def __init__(
        self,
        session: AsyncSession,
        repo: AssessmentRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or AssessmentRepository(session), audit_service=audit_service
        )

    async def create(
        self, institution_id: uuid.UUID, data: AssessmentCreate, *, created_by: uuid.UUID | None
    ) -> Assessment:
        # Local imports: `SubjectRepository` (Module 03), `AssessmentTypeRepository`,
        # and `AssessmentStatusRepository` may be owned by sibling agents in this
        # same wave and may not exist on disk yet when this module is first
        # imported — kept local so this file stays importable regardless of
        # import order (same pattern as `class_schedule_service.py`).
        from app.repositories.assessment_status_repository import AssessmentStatusRepository
        from app.repositories.assessment_type_repository import AssessmentTypeRepository
        from app.repositories.subject_repository import SubjectRepository

        subject = await SubjectRepository(self.session).get_by_id_for_institution(
            data.subject_id, institution_id
        )
        if subject is None:
            raise NotFoundError("Subject not found.")

        assessment_type = await AssessmentTypeRepository(self.session).get_by_id_for_institution(
            data.assessment_type_id, institution_id
        )
        if assessment_type is None:
            raise NotFoundError("Assessment type not found.")

        assessment_status = await AssessmentStatusRepository(
            self.session
        ).get_by_id_for_institution(data.assessment_status_id, institution_id)
        if assessment_status is None:
            raise NotFoundError("Assessment status not found.")

        assessment = Assessment(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        assessment = await self.repo.add(assessment)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, assessment.id)
        return assessment

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: AssessmentUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> Assessment:
        from app.repositories.assessment_status_repository import AssessmentStatusRepository
        from app.repositories.assessment_type_repository import AssessmentTypeRepository
        from app.repositories.subject_repository import SubjectRepository

        assessment = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "subject_id" in updates:
            subject = await SubjectRepository(self.session).get_by_id_for_institution(
                updates["subject_id"], institution_id
            )
            if subject is None:
                raise NotFoundError("Subject not found.")

        if "assessment_type_id" in updates:
            assessment_type = await AssessmentTypeRepository(
                self.session
            ).get_by_id_for_institution(updates["assessment_type_id"], institution_id)
            if assessment_type is None:
                raise NotFoundError("Assessment type not found.")

        if "assessment_status_id" in updates:
            assessment_status = await AssessmentStatusRepository(
                self.session
            ).get_by_id_for_institution(updates["assessment_status_id"], institution_id)
            if assessment_status is None:
                raise NotFoundError("Assessment status not found.")

        for field, value in updates.items():
            setattr(assessment, field, value)
        assessment.updated_by = updated_by
        if updates:
            assessment.current_version += 1
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(assessment)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, assessment.id)
        return assessment
