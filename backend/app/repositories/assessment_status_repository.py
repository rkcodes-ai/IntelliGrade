"""Persistence access for `AssessmentStatus`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment_status import AssessmentStatus
from app.repositories.tenant_repository import TenantScopedRepository


class AssessmentStatusRepository(TenantScopedRepository[AssessmentStatus]):
    search_fields = ("name", "code")
    sortable_fields = ("name", "code", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AssessmentStatus, session)
