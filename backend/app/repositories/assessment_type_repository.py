"""Persistence access for `AssessmentType`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment_type import AssessmentType
from app.repositories.tenant_repository import TenantScopedRepository


class AssessmentTypeRepository(TenantScopedRepository[AssessmentType]):
    search_fields = ("name", "code")
    sortable_fields = ("name", "code", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AssessmentType, session)
