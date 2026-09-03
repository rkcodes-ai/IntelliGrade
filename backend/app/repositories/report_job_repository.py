"""Persistence access for `ReportJob` (Module 07)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report_job import ReportJob
from app.repositories.tenant_repository import TenantScopedRepository


class ReportJobRepository(TenantScopedRepository[ReportJob]):
    sortable_fields = ("created_at", "updated_at", "status", "report_type")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ReportJob, session)
