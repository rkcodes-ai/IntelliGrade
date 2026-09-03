"""
Rubric management service.

Business rule enforced here (not the database): if `question_id` is
provided, it must reference an existing `Question` in the same institution;
a rubric without `question_id` is a reusable template, not yet attached to
any question, and requires no such check. Updates that touch a
content-bearing field (`name`, `total_marks`) bump `current_version` (see
`VersionCounterMixin`), mirroring `QuestionService.update`'s convention.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError
from app.models.rubric import Rubric
from app.repositories.rubric_repository import RubricRepository
from app.schemas.rubric import RubricCreate, RubricUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class RubricService(TenantScopedService[Rubric]):
    resource_type = "rubric"

    def __init__(
        self,
        session: AsyncSession,
        repo: RubricRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session, repo or RubricRepository(session), audit_service=audit_service)

    async def create(
        self, institution_id: uuid.UUID, data: RubricCreate, *, created_by: uuid.UUID | None
    ) -> Rubric:
        if data.question_id is not None:
            # Local import: `Question` is a Wave 1 sibling entity built in a
            # separate agent's file set; kept local for consistency with the
            # rest of this wave's cross-repository imports (see
            # `ClassScheduleService.create`'s `SubjectAllocationRepository`
            # import for the established pattern/rationale).
            from app.repositories.question_repository import QuestionRepository

            question = await QuestionRepository(self.session).get_by_id_for_institution(
                data.question_id, institution_id
            )
            if question is None:
                raise NotFoundError("Question not found.")

        rubric = Rubric(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        rubric = await self.repo.add(rubric)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, rubric.id)
        return rubric

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: RubricUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> Rubric:
        from app.repositories.question_repository import QuestionRepository

        rubric = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "question_id" in updates and updates["question_id"] is not None:
            question = await QuestionRepository(self.session).get_by_id_for_institution(
                updates["question_id"], institution_id
            )
            if question is None:
                raise NotFoundError("Question not found.")

        # A change to the graded content itself bumps the cheap version
        # counter (see `VersionCounterMixin`) — cosmetic changes (relinking
        # to a different question, toggling `is_active`) do not.
        bump_version = "name" in updates or "total_marks" in updates

        for field, value in updates.items():
            setattr(rubric, field, value)
        if bump_version:
            rubric.current_version += 1
        rubric.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(rubric)

        await self._log_audit(AuditAction.RUBRIC_UPDATED, updated_by, rubric.id)
        return rubric
