"""Persistence access for `ExamInstructions`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam_instructions import ExamInstructions
from app.repositories.tenant_repository import TenantScopedRepository


class ExamInstructionsRepository(TenantScopedRepository[ExamInstructions]):
    search_fields: tuple[str, ...] = ()
    sortable_fields = ("display_order", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ExamInstructions, session)
