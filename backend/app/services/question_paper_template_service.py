"""QuestionPaperTemplate management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError
from app.models.question_paper_template import QuestionPaperTemplate
from app.repositories.question_paper_template_repository import QuestionPaperTemplateRepository
from app.schemas.question_paper_template import (
    QuestionPaperTemplateCreate,
    QuestionPaperTemplateUpdate,
)
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class QuestionPaperTemplateService(TenantScopedService[QuestionPaperTemplate]):
    resource_type = "question_paper_template"

    def __init__(
        self,
        session: AsyncSession,
        repo: QuestionPaperTemplateRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or QuestionPaperTemplateRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: QuestionPaperTemplateCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> QuestionPaperTemplate:
        if await self.repo.code_exists(institution_id, "name", data.name):
            raise ConflictError("A question paper template with that name already exists.")

        template = QuestionPaperTemplate(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        template = await self.repo.add(template)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, template.id)
        return template

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: QuestionPaperTemplateUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> QuestionPaperTemplate:
        template = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "name" in updates and await self.repo.code_exists(
            institution_id, "name", updates["name"], exclude_id=entity_id
        ):
            raise ConflictError("A question paper template with that name already exists.")

        for field, value in updates.items():
            setattr(template, field, value)
        template.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(template)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, template.id)
        return template
