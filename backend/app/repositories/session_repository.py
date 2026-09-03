"""Persistence access for `Session` (user-visible logged-in-device records)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session
from app.repositories.base import BaseRepository


class SessionRepository(BaseRepository[Session]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Session, session)

    async def list_active_for_user(self, user_id: uuid.UUID) -> list[Session]:
        result = await self.session.execute(
            select(Session)
            .where(Session.user_id == user_id, Session.is_active.is_(True))
            .order_by(Session.last_active_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_family_id(self, family_id: uuid.UUID) -> Session | None:
        result = await self.session.execute(
            select(Session).where(Session.refresh_token_family_id == family_id)
        )
        return result.scalar_one_or_none()

    async def revoke(self, session_row: Session) -> None:
        session_row.is_active = False
        session_row.revoked_at = datetime.now(UTC)
        await self.session.flush()

    async def touch(self, session_row: Session) -> None:
        """Bump `last_active_at` — called on every successful token refresh."""
        session_row.last_active_at = datetime.now(UTC)
        await self.session.flush()
