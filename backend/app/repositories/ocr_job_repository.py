"""Persistence access for `OCRJob`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ocr_job import OCRJob
from app.repositories.tenant_repository import TenantScopedRepository


class OCRJobRepository(TenantScopedRepository[OCRJob]):
    search_fields = ("status", "celery_task_id")
    sortable_fields = ("created_at", "updated_at", "priority", "status")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(OCRJob, session)
