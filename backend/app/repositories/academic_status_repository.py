"""Persistence access for `AcademicStatus`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic_status import AcademicStatus
from app.repositories.tenant_repository import TenantScopedRepository


class AcademicStatusRepository(TenantScopedRepository[AcademicStatus]):
    search_fields = ("name", "code")
    sortable_fields = ("name", "code", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AcademicStatus, session)
