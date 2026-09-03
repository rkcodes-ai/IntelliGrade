"""NotificationEvent orchestration (Module 07). See ADR-046.

Storage-only framework: `create()` is called by other services at the
point an event happens (result published, evaluation ready for review,
...); there is no delivery channel here — see `KNOWN_LIMITATIONS.md`.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.models.notification_event import NotificationEvent
from app.repositories.notification_event_repository import NotificationEventRepository
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class NotificationService(TenantScopedService[NotificationEvent]):
    resource_type = "notification_event"

    def __init__(
        self,
        session: AsyncSession,
        repo: NotificationEventRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        repo = repo or NotificationEventRepository(session)
        super().__init__(session, repo, audit_service=audit_service)
        self._notification_repo = repo

    async def create(
        self,
        institution_id: uuid.UUID,
        *,
        recipient_user_id: uuid.UUID,
        event_type: str,
        payload: dict[str, Any] | None = None,
        actor_id: uuid.UUID | None,
    ) -> NotificationEvent:
        event = NotificationEvent(
            institution_id=institution_id,
            recipient_user_id=recipient_user_id,
            event_type=event_type,
            payload=payload,
        )
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        await self._log_audit(AuditAction.NOTIFICATION_CREATED, actor_id, event.id)
        return event

    async def list_for_current_user(
        self, institution_id: uuid.UUID, recipient_user_id: uuid.UUID, *, unread_only: bool = False
    ) -> list[NotificationEvent]:
        return await self._notification_repo.list_for_recipient(
            institution_id, recipient_user_id, unread_only=unread_only
        )

    async def mark_read(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> NotificationEvent:
        event = await self.get_by_id(institution_id, entity_id)
        event.is_read = True
        event.read_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def unread_count(self, institution_id: uuid.UUID, recipient_user_id: uuid.UUID) -> int:
        events = await self._notification_repo.list_for_recipient(
            institution_id, recipient_user_id, unread_only=True
        )
        return len(events)
