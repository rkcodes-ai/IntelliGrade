"""Persistence access for `NotificationEvent` (Module 07)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_event import NotificationEvent
from app.repositories.tenant_repository import TenantScopedRepository


class NotificationEventRepository(TenantScopedRepository[NotificationEvent]):
    sortable_fields = ("created_at", "is_read")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(NotificationEvent, session)

    async def list_for_recipient(
        self,
        institution_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        *,
        unread_only: bool = False,
    ) -> list[NotificationEvent]:
        query = select(NotificationEvent).where(
            NotificationEvent.institution_id == institution_id,
            NotificationEvent.recipient_user_id == recipient_user_id,
        )
        if unread_only:
            query = query.where(NotificationEvent.is_read.is_(False))
        query = query.order_by(NotificationEvent.created_at.desc())
        return list((await self.session.execute(query)).scalars().all())
