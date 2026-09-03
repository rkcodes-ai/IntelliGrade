"""Persistence access for `SubjectCategory`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subject_category import SubjectCategory
from app.repositories.tenant_repository import TenantScopedRepository


class SubjectCategoryRepository(TenantScopedRepository[SubjectCategory]):
    search_fields = ("name", "code")
    sortable_fields = ("name", "code", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SubjectCategory, session)
