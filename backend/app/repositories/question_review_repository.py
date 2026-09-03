"""Persistence access for `QuestionReview`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_review import QuestionReview
from app.repositories.tenant_repository import TenantScopedRepository


class QuestionReviewRepository(TenantScopedRepository[QuestionReview]):
    search_fields = ("comment",)
    sortable_fields = ("created_at", "updated_at", "rating")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(QuestionReview, session)
