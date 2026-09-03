"""QuestionPaper management service."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.question_paper import QuestionPaper
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.question_blueprint_repository import QuestionBlueprintRepository
from app.repositories.question_paper_repository import QuestionPaperRepository
from app.repositories.question_paper_template_repository import QuestionPaperTemplateRepository
from app.schemas.question_paper import QuestionPaperCreate, QuestionPaperUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService

#: `approval_status` values from which `submit_for_review()` is allowed.
_SUBMITTABLE_STATUSES = ("draft", "rejected")


class QuestionPaperService(TenantScopedService[QuestionPaper]):
    resource_type = "question_paper"

    def __init__(
        self,
        session: AsyncSession,
        repo: QuestionPaperRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or QuestionPaperRepository(session), audit_service=audit_service
        )

    async def create(
        self, institution_id: uuid.UUID, data: QuestionPaperCreate, *, created_by: uuid.UUID | None
    ) -> QuestionPaper:
        assessment = await AssessmentRepository(self.session).get_by_id_for_institution(
            data.assessment_id, institution_id
        )
        if assessment is None:
            raise NotFoundError("Assessment not found.")

        if data.blueprint_id is not None:
            blueprint = await QuestionBlueprintRepository(self.session).get_by_id_for_institution(
                data.blueprint_id, institution_id
            )
            if blueprint is None:
                raise NotFoundError("Question blueprint not found.")

        if data.template_id is not None:
            template = await QuestionPaperTemplateRepository(
                self.session
            ).get_by_id_for_institution(data.template_id, institution_id)
            if template is None:
                raise NotFoundError("Question paper template not found.")

        paper = QuestionPaper(
            institution_id=institution_id,
            **data.model_dump(),
            approval_status="draft",
            current_version=1,
            is_active=True,
            created_by=created_by,
        )
        paper = await self.repo.add(paper)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, paper.id)
        return paper

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: QuestionPaperUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> QuestionPaper:
        paper = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "assessment_id" in updates:
            assessment = await AssessmentRepository(self.session).get_by_id_for_institution(
                updates["assessment_id"], institution_id
            )
            if assessment is None:
                raise NotFoundError("Assessment not found.")

        if "blueprint_id" in updates and updates["blueprint_id"] is not None:
            blueprint = await QuestionBlueprintRepository(self.session).get_by_id_for_institution(
                updates["blueprint_id"], institution_id
            )
            if blueprint is None:
                raise NotFoundError("Question blueprint not found.")

        if "template_id" in updates and updates["template_id"] is not None:
            template = await QuestionPaperTemplateRepository(
                self.session
            ).get_by_id_for_institution(updates["template_id"], institution_id)
            if template is None:
                raise NotFoundError("Question paper template not found.")

        # A change to the graded content itself bumps the cheap version
        # counter (see `VersionCounterMixin`) — cosmetic/reference edits
        # (blueprint_id, template_id, is_active, ...) do not, exactly like
        # `QuestionService.update`'s `bump_version` rule.
        bump_version = "name" in updates or "total_marks" in updates

        for field, value in updates.items():
            setattr(paper, field, value)
        if bump_version:
            paper.current_version += 1
        paper.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(paper)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, paper.id)
        return paper

    async def submit_for_review(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> QuestionPaper:
        paper = await self.get_by_id(institution_id, entity_id)
        if paper.approval_status not in _SUBMITTABLE_STATUSES:
            raise ConflictError(
                "Only a draft or rejected question paper can be submitted for review."
            )

        paper.approval_status = "pending_review"
        paper.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(paper)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, actor_id, paper.id)
        return paper

    async def approve(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> QuestionPaper:
        paper = await self.get_by_id(institution_id, entity_id)
        if paper.approval_status != "pending_review":
            raise ConflictError("Only a question paper pending review can be approved.")

        paper.approval_status = "approved"
        paper.approved_by = actor_id
        paper.approved_at = datetime.now(UTC)
        paper.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(paper)

        await self._log_audit(AuditAction.QUESTION_PAPER_GENERATED, actor_id, paper.id)
        return paper

    async def reject(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        *,
        reason: str,
        actor_id: uuid.UUID | None,
    ) -> QuestionPaper:
        paper = await self.get_by_id(institution_id, entity_id)
        if paper.approval_status != "pending_review":
            raise ConflictError("Only a question paper pending review can be rejected.")

        paper.approval_status = "rejected"
        paper.rejection_reason = reason
        paper.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(paper)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, actor_id, paper.id)
        return paper
