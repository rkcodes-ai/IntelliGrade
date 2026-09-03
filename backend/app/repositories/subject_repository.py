"""Persistence access for `Subject`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subject import Subject
from app.repositories.tenant_repository import TenantScopedRepository


class SubjectRepository(TenantScopedRepository[Subject]):
    search_fields = ("name", "code")
    sortable_fields = ("name", "code", "semester_number", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Subject, session)
