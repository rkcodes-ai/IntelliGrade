"""Persistence access for `PasswordHistory` — powers reuse prevention."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.password_history import PasswordHistory
from app.repositories.base import BaseRepository


class PasswordHistoryRepository(BaseRepository[PasswordHistory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(PasswordHistory, session)

    async def list_recent(self, user_id: uuid.UUID, *, limit: int) -> list[PasswordHistory]:
        result = await self.session.execute(
            select(PasswordHistory)
            .where(PasswordHistory.user_id == user_id)
            .order_by(PasswordHistory.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def record(self, user_id: uuid.UUID, hashed_password: str) -> PasswordHistory:
        entry = PasswordHistory(user_id=user_id, hashed_password=hashed_password)
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def prune_beyond(self, user_id: uuid.UUID, *, keep: int) -> None:
        """Delete all but the `keep` most recent history rows for a user."""
        recent = await self.list_recent(user_id, limit=keep)
        if len(recent) < keep:
            return
        cutoff_created_at = recent[-1].created_at
        await self.session.execute(
            delete(PasswordHistory).where(
                PasswordHistory.user_id == user_id,
                PasswordHistory.created_at < cutoff_created_at,
            )
        )
        await self.session.flush()
