"""QuestionPaperQuestionMapping management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.question_paper_question_mapping import QuestionPaperQuestionMapping
from app.repositories.question_paper_question_mapping_repository import (
    QuestionPaperQuestionMappingRepository,
)
from app.schemas.question_paper_question_mapping import (
    QuestionPaperQuestionMappingCreate,
    QuestionPaperQuestionMappingUpdate,
)
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class QuestionPaperQuestionMappingService(TenantScopedService[QuestionPaperQuestionMapping]):
    resource_type = "question_paper_question_mapping"

    def __init__(
        self,
        session: AsyncSession,
        repo: QuestionPaperQuestionMappingRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        repo = repo or QuestionPaperQuestionMappingRepository(session)
        super().__init__(session, repo, audit_service=audit_service)
        self._mapping_repo = repo

    async def create(
        self,
        institution_id: uuid.UUID,
        data: QuestionPaperQuestionMappingCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> QuestionPaperQuestionMapping:
        # QuestionPaperSectionRepository is a sibling written by this same
        # agent as part of this same task, so it already exists on disk —
        # no forward-reference concern, but kept as a local import for
        # symmetry with the QuestionRepository import below.
        from app.repositories.question_paper_section_repository import (
            QuestionPaperSectionRepository,
        )
        from app.repositories.question_repository import QuestionRepository

        section = await QuestionPaperSectionRepository(self.session).get_by_id_for_institution(
            data.question_paper_section_id, institution_id
        )
        if section is None:
            raise NotFoundError("Question paper section not found.")

        question = await QuestionRepository(self.session).get_by_id_for_institution(
            data.question_id, institution_id
        )
        if question is None:
            raise NotFoundError("Question not found.")

        if await self._mapping_repo.mapping_exists(
            institution_id, data.question_paper_section_id, data.question_id
        ):
            raise ConflictError("This question is already mapped into this section.")

        mapping = QuestionPaperQuestionMapping(
            institution_id=institution_id,
            **data.model_dump(),
            created_by=created_by,
        )
        mapping = await self.repo.add(mapping)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, mapping.id)
        return mapping

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: QuestionPaperQuestionMappingUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> QuestionPaperQuestionMapping:
        from app.repositories.question_paper_section_repository import (
            QuestionPaperSectionRepository,
        )
        from app.repositories.question_repository import QuestionRepository

        mapping = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "question_paper_section_id" in updates:
            section = await QuestionPaperSectionRepository(self.session).get_by_id_for_institution(
                updates["question_paper_section_id"], institution_id
            )
            if section is None:
                raise NotFoundError("Question paper section not found.")

        if "question_id" in updates:
            question = await QuestionRepository(self.session).get_by_id_for_institution(
                updates["question_id"], institution_id
            )
            if question is None:
                raise NotFoundError("Question not found.")

        if "question_paper_section_id" in updates or "question_id" in updates:
            target_section_id = updates.get(
                "question_paper_section_id", mapping.question_paper_section_id
            )
            target_question_id = updates.get("question_id", mapping.question_id)
            if await self._mapping_repo.mapping_exists(
                institution_id, target_section_id, target_question_id, exclude_id=entity_id
            ):
                raise ConflictError("This question is already mapped into this section.")

        for field, value in updates.items():
            setattr(mapping, field, value)
        mapping.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(mapping)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, mapping.id)
        return mapping
