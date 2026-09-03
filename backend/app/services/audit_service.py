"""Audit logging service — the single write path for `audit_logs`."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.repositories.audit_log_repository import AuditLogRepository
from app.services.base import BaseService


class AuditService(BaseService):
    def __init__(
        self, session: AsyncSession, audit_log_repo: AuditLogRepository | None = None
    ) -> None:
        super().__init__(session)
        self.audit_log_repo = audit_log_repo or AuditLogRepository(session)

    async def log(
        self,
        *,
        action: str,
        status: str,
        user_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AuditLog:
        """
        Record one security-relevant event. Callers pass whatever request
        context they have (IP/user agent/request ID come from the endpoint
        layer — services never reach into `Request` directly, keeping them
        HTTP-agnostic per `docs/architecture.md`'s layering rule).
        """
        entry = await self.audit_log_repo.record(
            action=action,
            status=status,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            context=context,
        )
        self.logger.info(
            "audit_event",
            action=action,
            status=status,
            user_id=str(user_id) if user_id else None,
            request_id=request_id,
        )
        return entry
