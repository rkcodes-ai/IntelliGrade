"""QuestionReview management service — informal peer feedback on a `Question`."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError
from app.models.question_review import QuestionReview
from app.repositories.question_review_repository import QuestionReviewRepository
from app.schemas.question_review import QuestionReviewCreate, QuestionReviewUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class QuestionReviewService(TenantScopedService[QuestionReview]):
    resource_type = "question_review"

    def __init__(
        self,
        session: AsyncSession,
        repo: QuestionReviewRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or QuestionReviewRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: QuestionReviewCreate,
        *,
        reviewer_id: uuid.UUID | None,
        created_by: uuid.UUID | None,
    ) -> QuestionReview:
        # Local import: sibling repository, see `QuestionService.create()`'s comment.
        from app.repositories.question_repository import QuestionRepository

        question = await QuestionRepository(self.session).get_by_id_for_institution(
            data.question_id, institution_id
        )
        if question is None:
            raise NotFoundError("Question not found.")

        review = QuestionReview(
            institution_id=institution_id,
            question_id=data.question_id,
            reviewer_id=reviewer_id,
            comment=data.comment,
            rating=data.rating,
            created_by=created_by,
        )
        review = await self.repo.add(review)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, review.id)
        return review

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: QuestionReviewUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> QuestionReview:
        review = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(review, field, value)
        review.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(review)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, review.id)
        return review
