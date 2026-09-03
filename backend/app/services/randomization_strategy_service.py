"""RandomizationStrategy management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.randomization_strategy import RandomizationStrategy
from app.repositories.randomization_strategy_repository import RandomizationStrategyRepository
from app.schemas.randomization_strategy import (
    RandomizationStrategyCreate,
    RandomizationStrategyUpdate,
)
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class RandomizationStrategyService(TenantScopedService[RandomizationStrategy]):
    resource_type = "randomization_strategy"

    def __init__(
        self,
        session: AsyncSession,
        repo: RandomizationStrategyRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or RandomizationStrategyRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: RandomizationStrategyCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> RandomizationStrategy:
        # Local imports: `QuestionPaperRepository` is owned by a sibling
        # agent in this same wave and may not exist on disk yet when this
        # module is first imported. `QuestionPaperSectionRepository` is
        # written by this same agent (so it does exist), but is kept local
        # too for symmetry with the sibling import above.
        from app.repositories.question_paper_repository import QuestionPaperRepository
        from app.repositories.question_paper_section_repository import (
            QuestionPaperSectionRepository,
        )

        if data.question_paper_id is None and data.question_paper_section_id is None:
            raise ValidationAppError(
                "At least one of question_paper_id or question_paper_section_id must be set."
            )

        if data.question_paper_id is not None:
            paper = await QuestionPaperRepository(self.session).get_by_id_for_institution(
                data.question_paper_id, institution_id
            )
            if paper is None:
                raise NotFoundError("Question paper not found.")

        if data.question_paper_section_id is not None:
            section = await QuestionPaperSectionRepository(self.session).get_by_id_for_institution(
                data.question_paper_section_id, institution_id
            )
            if section is None:
                raise NotFoundError("Question paper section not found.")

        strategy = RandomizationStrategy(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        strategy = await self.repo.add(strategy)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, strategy.id)
        return strategy

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: RandomizationStrategyUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> RandomizationStrategy:
        from app.repositories.question_paper_repository import QuestionPaperRepository
        from app.repositories.question_paper_section_repository import (
            QuestionPaperSectionRepository,
        )

        strategy = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "question_paper_id" in updates and updates["question_paper_id"] is not None:
            paper = await QuestionPaperRepository(self.session).get_by_id_for_institution(
                updates["question_paper_id"], institution_id
            )
            if paper is None:
                raise NotFoundError("Question paper not found.")

        if (
            "question_paper_section_id" in updates
            and updates["question_paper_section_id"] is not None
        ):
            section = await QuestionPaperSectionRepository(self.session).get_by_id_for_institution(
                updates["question_paper_section_id"], institution_id
            )
            if section is None:
                raise NotFoundError("Question paper section not found.")

        target_paper_id = updates.get("question_paper_id", strategy.question_paper_id)
        target_section_id = updates.get(
            "question_paper_section_id", strategy.question_paper_section_id
        )
        if target_paper_id is None and target_section_id is None:
            raise ValidationAppError(
                "At least one of question_paper_id or question_paper_section_id must be set."
            )

        for field, value in updates.items():
            setattr(strategy, field, value)
        strategy.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(strategy)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, strategy.id)
        return strategy
