"""ProcessingHistory management service — append-only per-stage transition log."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.processing_history import ProcessingHistory
from app.repositories.processing_history_repository import ProcessingHistoryRepository
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class ProcessingHistoryService(TenantScopedService[ProcessingHistory]):
    resource_type = "processing_history"

    def __init__(
        self,
        session: AsyncSession,
        repo: ProcessingHistoryRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or ProcessingHistoryRepository(session), audit_service=audit_service
        )

    async def record(
        self,
        institution_id: uuid.UUID,
        answer_script_id: uuid.UUID,
        *,
        stage: str,
        from_status: str | None = None,
        to_status: str,
        duration_ms: int | None = None,
        error_detail: str | None = None,
        triggered_by: str = "system",
    ) -> ProcessingHistory:
        """
        Persists + flushes one stage-transition row (no commit -- callers
        own the transaction boundary, matching every other service method
        in this codebase). Meant to be called directly by pipeline/task
        code (built centrally, not part of this delegation) -- no HTTP
        route calls this (see `app/api/v1/endpoints/processing_history.py`).

        Per ADR-030 this table IS the pipeline's own stage-transition log,
        so unlike every mutating method on `TenantScopedService` subclasses
        elsewhere in this codebase, this deliberately does NOT also write
        an `AuditLog` entry via `self._log_audit` -- that's reserved for
        human-initiated actions.
        """
        entry = ProcessingHistory(
            institution_id=institution_id,
            answer_script_id=answer_script_id,
            stage=stage,
            from_status=from_status,
            to_status=to_status,
            duration_ms=duration_ms,
            error_detail=error_detail,
            triggered_by=triggered_by,
        )
        return await self.repo.add(entry)
