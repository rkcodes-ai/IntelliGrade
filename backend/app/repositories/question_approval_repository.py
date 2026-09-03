"""Persistence access for `QuestionApproval`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_approval import QuestionApproval
from app.repositories.tenant_repository import TenantScopedRepository


class QuestionApprovalRepository(TenantScopedRepository[QuestionApproval]):
    search_fields = ("decision", "comments")
    sortable_fields = ("created_at", "updated_at", "reviewed_at", "decision")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(QuestionApproval, session)
