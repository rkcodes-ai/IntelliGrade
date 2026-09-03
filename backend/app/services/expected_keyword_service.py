"""
ExpectedKeyword management service.

Business rule enforced here (not the database): exactly one of
`answer_key_id`/`rubric_criterion_id` must be set, and whichever one is set
must reference an existing row in the same institution.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.expected_keyword import ExpectedKeyword
from app.repositories.expected_keyword_repository import ExpectedKeywordRepository
from app.repositories.rubric_criterion_repository import RubricCriterionRepository
from app.schemas.expected_keyword import ExpectedKeywordCreate, ExpectedKeywordUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class ExpectedKeywordService(TenantScopedService[ExpectedKeyword]):
    resource_type = "expected_keyword"

    def __init__(
        self,
        session: AsyncSession,
        repo: ExpectedKeywordRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or ExpectedKeywordRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: ExpectedKeywordCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> ExpectedKeyword:
        await self._validate_parent(institution_id, data.answer_key_id, data.rubric_criterion_id)

        keyword = ExpectedKeyword(
            institution_id=institution_id,
            **data.model_dump(),
            created_by=created_by,
        )
        keyword = await self.repo.add(keyword)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, keyword.id)
        return keyword

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: ExpectedKeywordUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> ExpectedKeyword:
        keyword = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "answer_key_id" in updates or "rubric_criterion_id" in updates:
            target_answer_key_id = updates.get("answer_key_id", keyword.answer_key_id)
            target_rubric_criterion_id = updates.get(
                "rubric_criterion_id", keyword.rubric_criterion_id
            )
            await self._validate_parent(
                institution_id, target_answer_key_id, target_rubric_criterion_id
            )

        for field, value in updates.items():
            setattr(keyword, field, value)
        keyword.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(keyword)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, keyword.id)
        return keyword

    async def _validate_parent(
        self,
        institution_id: uuid.UUID,
        answer_key_id: uuid.UUID | None,
        rubric_criterion_id: uuid.UUID | None,
    ) -> None:
        if (answer_key_id is None) == (rubric_criterion_id is None):
            raise ValidationAppError(
                "Exactly one of answer_key_id or rubric_criterion_id must be set."
            )

        if answer_key_id is not None:
            # Local import: `AnswerKey`/`AnswerKeyRepository` are owned by a
            # sibling agent in this same wave and may not exist on disk yet
            # when this module is first imported — kept local so this file
            # stays importable regardless of import order (same pattern as
            # `ClassScheduleService.create`'s `SubjectAllocationRepository`
            # import).
            from app.repositories.answer_key_repository import AnswerKeyRepository

            answer_key = await AnswerKeyRepository(self.session).get_by_id_for_institution(
                answer_key_id, institution_id
            )
            if answer_key is None:
                raise NotFoundError("Answer key not found.")
        elif rubric_criterion_id is not None:
            criterion = await RubricCriterionRepository(self.session).get_by_id_for_institution(
                rubric_criterion_id, institution_id
            )
            if criterion is None:
                raise NotFoundError("Rubric criterion not found.")
