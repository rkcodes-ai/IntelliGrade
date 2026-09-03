"""
AnswerKey management service.

`AnswerKey` is the single authoritative answer key for a `Question` — a
strict 1:1 relationship. `create()` validates `question_id` references an
existing `Question` in the same institution and pre-checks the 1:1
constraint (the model's `unique=True` on `question_id` also enforces this
at the database level; the pre-check here exists to return a clean 409
instead of a raw integrity error) — same pattern as
`AssessmentConfigurationService.create`
(`app/services/assessment_configuration_service.py`).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.answer_key import AnswerKey
from app.repositories.answer_key_repository import AnswerKeyRepository
from app.schemas.answer_key import AnswerKeyCreate, AnswerKeyUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class AnswerKeyService(TenantScopedService[AnswerKey]):
    resource_type = "answer_key"

    def __init__(
        self,
        session: AsyncSession,
        repo: AnswerKeyRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session, repo or AnswerKeyRepository(session), audit_service=audit_service)

    async def create(
        self, institution_id: uuid.UUID, data: AnswerKeyCreate, *, created_by: uuid.UUID | None
    ) -> AnswerKey:
        # Local import: `Question`/`QuestionRepository` come from an earlier
        # wave, but kept local for consistency with every other
        # cross-entity parent lookup in this wave (see
        # `ClassScheduleService.create`'s `SubjectAllocationRepository`
        # import for the reasoning).
        from app.repositories.question_repository import QuestionRepository

        question = await QuestionRepository(self.session).get_by_id_for_institution(
            data.question_id, institution_id
        )
        if question is None:
            raise NotFoundError("Question not found.")

        if await self.repo.code_exists(
            institution_id,
            "question_id",
            data.question_id,  # type: ignore[arg-type] # code_exists's code_value is
            # typed `str` but does a plain `==` comparison, so it works for any column
            # type — see TenantScopedRepository.code_exists docstring.
        ):
            raise ConflictError("An answer key already exists for this question.")

        answer_key = AnswerKey(
            institution_id=institution_id,
            **data.model_dump(),
            current_version=1,
            created_by=created_by,
        )
        answer_key = await self.repo.add(answer_key)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, answer_key.id)
        return answer_key

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: AnswerKeyUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> AnswerKey:
        answer_key = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        # A change to the graded content itself bumps the cheap version
        # counter (see `VersionCounterMixin`) — other fields (expected
        # length/structure, evaluation notes, ...) do not.
        bump_version = "reference_answer" in updates

        for field, value in updates.items():
            setattr(answer_key, field, value)
        if bump_version:
            answer_key.current_version += 1
        answer_key.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(answer_key)

        await self._log_audit(AuditAction.ANSWER_KEY_UPDATED, updated_by, answer_key.id)
        return answer_key
