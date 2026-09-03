"""OCRJob management service — one OCR execution attempt against an AnswerScript."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError
from app.models.ocr_job import OCRJob
from app.repositories.ocr_job_repository import OCRJobRepository
from app.schemas.ocr_job import OCRJobCreate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService

#: Statuses from which a job may still transition to `"cancelled"`.
_CANCELLABLE_STATUSES = ("queued", "running")


class OCRJobService(TenantScopedService[OCRJob]):
    resource_type = "ocr_job"

    def __init__(
        self,
        session: AsyncSession,
        repo: OCRJobRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session, repo or OCRJobRepository(session), audit_service=audit_service)

    async def create(
        self,
        institution_id: uuid.UUID,
        data: OCRJobCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> OCRJob:
        """
        Persists a new job row in `"queued"` status only. Deliberately does
        NOT import anything from `app.tasks` or enqueue a Celery task --
        that wiring (a `celery_app.send_task(...)` call that then populates
        `celery_task_id`) is added centrally later by someone else, once
        the actual OCR Celery task exists.
        """
        job = OCRJob(
            institution_id=institution_id,
            answer_script_id=data.answer_script_id,
            ocr_provider_id=data.ocr_provider_id,
            status="queued",
            priority=data.priority,
            max_retries=data.max_retries,
            created_by=created_by,
        )
        job = await self.repo.add(job)
        await self._log_audit(AuditAction.OCR_EXECUTION_STARTED, created_by, job.id)
        return job

    async def cancel(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        *,
        actor_id: uuid.UUID | None,
    ) -> OCRJob:
        """Only valid from `"queued"`/`"running"` -- else a 409 `ConflictError`."""
        job = await self.get_by_id(institution_id, entity_id)
        if job.status not in _CANCELLABLE_STATUSES:
            raise ConflictError(
                f"Cannot cancel an OCR job in '{job.status}' status "
                f"(only {' or '.join(_CANCELLABLE_STATUSES)} jobs may be cancelled)."
            )
        job.status = "cancelled"
        job.updated_by = actor_id
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(job)
        await self._log_audit(AuditAction.OCR_JOB_CANCELLED, actor_id, job.id)
        return job
