"""Persistence access for `Exam`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam import Exam
from app.repositories.tenant_repository import TenantScopedRepository


class ExamRepository(TenantScopedRepository[Exam]):
    search_fields = ("name",)
    sortable_fields = ("name", "exam_date", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Exam, session)
