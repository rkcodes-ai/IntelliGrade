"""Question management service."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.question import Question
from app.models.question_tag_map import QuestionTagMap
from app.repositories.question_repository import QuestionRepository
from app.repositories.question_tag_map_repository import QuestionTagMapRepository
from app.repositories.subject_repository import SubjectRepository
from app.schemas.question import QuestionCreate, QuestionUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService

#: `approval_status` values from which `submit_for_review()` is allowed.
_SUBMITTABLE_STATUSES = ("draft", "rejected")


class QuestionService(TenantScopedService[Question]):
    resource_type = "question"

    def __init__(
        self,
        session: AsyncSession,
        repo: QuestionRepository | None = None,
        tag_map_repo: QuestionTagMapRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session, repo or QuestionRepository(session), audit_service=audit_service)
        self._tag_map_repo = tag_map_repo or QuestionTagMapRepository(session)

    async def create(
        self, institution_id: uuid.UUID, data: QuestionCreate, *, created_by: uuid.UUID | None
    ) -> Question:
        # Local imports: these sibling lookup-table repositories are owned
        # by other agents in this same wave and may not exist on disk yet
        # when this module is first imported — kept local so this file
        # stays importable regardless of import order, exactly like
        # `ClassScheduleService`'s `SubjectAllocationRepository` import.
        from app.repositories.bloom_taxonomy_level_repository import BloomTaxonomyLevelRepository
        from app.repositories.difficulty_level_repository import DifficultyLevelRepository
        from app.repositories.question_category_repository import QuestionCategoryRepository
        from app.repositories.question_type_repository import QuestionTypeRepository

        subject = await SubjectRepository(self.session).get_by_id_for_institution(
            data.subject_id, institution_id
        )
        if subject is None:
            raise NotFoundError("Subject not found.")

        category = await QuestionCategoryRepository(self.session).get_by_id_for_institution(
            data.question_category_id, institution_id
        )
        if category is None:
            raise NotFoundError("Question category not found.")

        question_type = await QuestionTypeRepository(self.session).get_by_id_for_institution(
            data.question_type_id, institution_id
        )
        if question_type is None:
            raise NotFoundError("Question type not found.")

        difficulty_level = await DifficultyLevelRepository(self.session).get_by_id_for_institution(
            data.difficulty_level_id, institution_id
        )
        if difficulty_level is None:
            raise NotFoundError("Difficulty level not found.")

        bloom_level = await BloomTaxonomyLevelRepository(self.session).get_by_id_for_institution(
            data.bloom_level_id, institution_id
        )
        if bloom_level is None:
            raise NotFoundError("Bloom taxonomy level not found.")

        question = Question(
            institution_id=institution_id,
            **data.model_dump(),
            approval_status="draft",
            current_version=1,
            is_active=True,
            created_by=created_by,
        )
        question = await self.repo.add(question)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, question.id)
        return question

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: QuestionUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> Question:
        from app.repositories.bloom_taxonomy_level_repository import BloomTaxonomyLevelRepository
        from app.repositories.difficulty_level_repository import DifficultyLevelRepository
        from app.repositories.question_category_repository import QuestionCategoryRepository
        from app.repositories.question_type_repository import QuestionTypeRepository

        question = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "subject_id" in updates:
            subject = await SubjectRepository(self.session).get_by_id_for_institution(
                updates["subject_id"], institution_id
            )
            if subject is None:
                raise NotFoundError("Subject not found.")

        if "question_category_id" in updates:
            category = await QuestionCategoryRepository(self.session).get_by_id_for_institution(
                updates["question_category_id"], institution_id
            )
            if category is None:
                raise NotFoundError("Question category not found.")

        if "question_type_id" in updates:
            question_type = await QuestionTypeRepository(self.session).get_by_id_for_institution(
                updates["question_type_id"], institution_id
            )
            if question_type is None:
                raise NotFoundError("Question type not found.")

        if "difficulty_level_id" in updates:
            difficulty_level = await DifficultyLevelRepository(
                self.session
            ).get_by_id_for_institution(updates["difficulty_level_id"], institution_id)
            if difficulty_level is None:
                raise NotFoundError("Difficulty level not found.")

        if "bloom_level_id" in updates:
            bloom_level = await BloomTaxonomyLevelRepository(
                self.session
            ).get_by_id_for_institution(updates["bloom_level_id"], institution_id)
            if bloom_level is None:
                raise NotFoundError("Bloom taxonomy level not found.")

        # A change to the graded content itself bumps the cheap version
        # counter (see `VersionCounterMixin`) — cosmetic/classification
        # field edits (unit, tags, difficulty, ...) do not.
        bump_version = "question_text" in updates or "marks" in updates

        for field, value in updates.items():
            setattr(question, field, value)
        if bump_version:
            question.current_version += 1
        question.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(question)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, question.id)
        return question

    async def submit_for_review(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> Question:
        question = await self.get_by_id(institution_id, entity_id)
        if question.approval_status not in _SUBMITTABLE_STATUSES:
            raise ConflictError("Only a draft or rejected question can be submitted for review.")

        question.approval_status = "pending_review"
        question.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(question)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, actor_id, question.id)
        return question

    async def approve(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> Question:
        question = await self.get_by_id(institution_id, entity_id)
        if question.approval_status != "pending_review":
            raise ConflictError("Only a question pending review can be approved.")

        question.approval_status = "approved"
        question.approved_by = actor_id
        question.approved_at = datetime.now(UTC)
        question.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(question)

        await self._log_audit(AuditAction.QUESTION_APPROVED, actor_id, question.id)
        return question

    async def reject(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        *,
        reason: str,
        actor_id: uuid.UUID | None,
    ) -> Question:
        question = await self.get_by_id(institution_id, entity_id)
        if question.approval_status != "pending_review":
            raise ConflictError("Only a question pending review can be rejected.")

        question.approval_status = "rejected"
        question.rejection_reason = reason
        question.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(question)

        await self._log_audit(AuditAction.QUESTION_REJECTED, actor_id, question.id)
        return question

    async def add_tag(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, tag_id: uuid.UUID
    ) -> QuestionTagMap:
        # Local import: sibling lookup repository, see `create()`'s comment.
        from app.repositories.question_tag_repository import QuestionTagRepository

        question = await self.get_by_id(institution_id, entity_id)

        tag = await QuestionTagRepository(self.session).get_by_id_for_institution(
            tag_id, institution_id
        )
        if tag is None:
            raise NotFoundError("Question tag not found.")

        existing = await self._tag_map_repo.get_by_question_and_tag(question.id, tag_id)
        if existing is not None:
            raise ConflictError("This tag is already mapped to this question.")

        tag_map = QuestionTagMap(
            institution_id=institution_id, question_id=question.id, tag_id=tag_id
        )
        return await self._tag_map_repo.add(tag_map)

    async def remove_tag(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, tag_id: uuid.UUID
    ) -> None:
        question = await self.get_by_id(institution_id, entity_id)
        tag_map = await self._tag_map_repo.get_by_question_and_tag(question.id, tag_id)
        if tag_map is None:
            raise NotFoundError("This tag is not mapped to this question.")
        await self._tag_map_repo.remove(tag_map)
