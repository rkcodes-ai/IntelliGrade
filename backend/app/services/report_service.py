"""ReportJob orchestration (Module 07, Feature 8). See ADR-045.

`create_job` only persists the `ReportJob` row in `"pending"` status — it
does not import anything from `app.tasks` or enqueue the Celery task
itself, same separation `OCRJobService`/`OfficialExamDocumentService`
already established (dispatch happens in the endpoint, via a
best-effort `.delay()` wrapper that swallows broker-connectivity
failures).
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.models.report_job import ReportJob
from app.repositories.report_job_repository import ReportJobRepository
from app.schemas.report_job import ReportFormat, ReportType
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class ReportService(TenantScopedService[ReportJob]):
    resource_type = "report_job"

    def __init__(
        self,
        session: AsyncSession,
        repo: ReportJobRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        repo = repo or ReportJobRepository(session)
        super().__init__(session, repo, audit_service=audit_service)

    async def create_job(
        self,
        institution_id: uuid.UUID,
        *,
        report_type: ReportType,
        format: ReportFormat,
        parameters: dict[str, Any] | None,
        actor_id: uuid.UUID | None,
    ) -> ReportJob:
        job = ReportJob(
            institution_id=institution_id,
            report_type=report_type,
            format=format,
            parameters=parameters,
            requested_by=actor_id,
            created_by=actor_id,
        )
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        await self._log_audit(AuditAction.REPORT_GENERATED, actor_id, job.id)
        return job
