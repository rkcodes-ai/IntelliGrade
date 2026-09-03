"""UploadJob service — read-mostly; rows are written internally by
`AnswerScriptService.upload()`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.upload_job import UploadJob
from app.repositories.upload_job_repository import UploadJobRepository
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class UploadJobService(TenantScopedService[UploadJob]):
    resource_type = "upload_job"

    def __init__(
        self,
        session: AsyncSession,
        repo: UploadJobRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session, repo or UploadJobRepository(session), audit_service=audit_service)
