"""
ExpectedConcept management service.

Business rule enforced here (not the database): exactly one of
`answer_key_id`/`rubric_criterion_id` must be set, and whichever one is set
must reference an existing row in the same institution. Mirrors
`ExpectedKeywordService` exactly (see that service's docstring/comments for
the full rationale).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.expected_concept import ExpectedConcept
from app.repositories.expected_concept_repository import ExpectedConceptRepository
from app.repositories.rubric_criterion_repository import RubricCriterionRepository
from app.schemas.expected_concept import ExpectedConceptCreate, ExpectedConceptUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class ExpectedConceptService(TenantScopedService[ExpectedConcept]):
    resource_type = "expected_concept"

    def __init__(
        self,
        session: AsyncSession,
        repo: ExpectedConceptRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or ExpectedConceptRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: ExpectedConceptCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> ExpectedConcept:
        await self._validate_parent(institution_id, data.answer_key_id, data.rubric_criterion_id)

        concept = ExpectedConcept(
            institution_id=institution_id,
            **data.model_dump(),
            created_by=created_by,
        )
        concept = await self.repo.add(concept)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, concept.id)
        return concept

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: ExpectedConceptUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> ExpectedConcept:
        concept = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "answer_key_id" in updates or "rubric_criterion_id" in updates:
            target_answer_key_id = updates.get("answer_key_id", concept.answer_key_id)
            target_rubric_criterion_id = updates.get(
                "rubric_criterion_id", concept.rubric_criterion_id
            )
            await self._validate_parent(
                institution_id, target_answer_key_id, target_rubric_criterion_id
            )

        for field, value in updates.items():
            setattr(concept, field, value)
        concept.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(concept)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, concept.id)
        return concept

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
            # Local import: see `ExpectedKeywordService._validate_parent`'s
            # comment for the full rationale — `AnswerKey` is a sibling
            # wave entity that may not exist on disk yet.
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
