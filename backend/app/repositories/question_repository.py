"""Persistence access for `Question`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question
from app.repositories.tenant_repository import TenantScopedRepository


class QuestionRepository(TenantScopedRepository[Question]):
    search_fields = ("question_text", "topic", "chapter", "unit")
    sortable_fields = (
        "created_at",
        "updated_at",
        "marks",
        "estimated_time_minutes",
        "current_version",
        "approval_status",
    )

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Question, session)
