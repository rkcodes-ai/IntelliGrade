"""QuestionPaperSection management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError
from app.models.question_paper_section import QuestionPaperSection
from app.repositories.question_paper_section_repository import QuestionPaperSectionRepository
from app.schemas.question_paper_section import (
    QuestionPaperSectionCreate,
    QuestionPaperSectionUpdate,
)
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class QuestionPaperSectionService(TenantScopedService[QuestionPaperSection]):
    resource_type = "question_paper_section"

    def __init__(
        self,
        session: AsyncSession,
        repo: QuestionPaperSectionRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or QuestionPaperSectionRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: QuestionPaperSectionCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> QuestionPaperSection:
        # Local import: QuestionPaper is owned by a sibling agent in this
        # same wave and may not exist on disk yet when this module is first
        # imported — kept local so this file stays importable regardless of
        # import order, same pattern as `class_schedule_service.py`.
        from app.repositories.question_paper_repository import QuestionPaperRepository

        paper = await QuestionPaperRepository(self.session).get_by_id_for_institution(
            data.question_paper_id, institution_id
        )
        if paper is None:
            raise NotFoundError("Question paper not found.")

        section = QuestionPaperSection(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        section = await self.repo.add(section)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, section.id)
        return section

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: QuestionPaperSectionUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> QuestionPaperSection:
        from app.repositories.question_paper_repository import QuestionPaperRepository

        section = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "question_paper_id" in updates:
            paper = await QuestionPaperRepository(self.session).get_by_id_for_institution(
                updates["question_paper_id"], institution_id
            )
            if paper is None:
                raise NotFoundError("Question paper not found.")

        for field, value in updates.items():
            setattr(section, field, value)
        section.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(section)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, section.id)
        return section
