"""
Session tracking service — the user-visible "logged in on these devices" list.

Distinct from `TokenService`: a `Session` row is the human-facing concept
(one per login, shown in the Session Management UI), while `RefreshToken`
rows are the machine-facing rotation chain backing it. They're linked by
`family_id`, not a foreign key, so token rotation (which creates new
`RefreshToken` rows constantly) never has to touch the `Session` row except
to bump `last_active_at`.
"""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.session import Session
from app.repositories.session_repository import SessionRepository
from app.services.base import BaseService


class SessionService(BaseService):
    def __init__(
        self, session: AsyncSession, session_repo: SessionRepository | None = None
    ) -> None:
        super().__init__(session)
        self.session_repo = session_repo or SessionRepository(session)

    async def start_session(
        self,
        user_id: uuid.UUID,
        family_id: uuid.UUID,
        *,
        expires_at: datetime,
        ip_address: str | None,
        user_agent: str | None,
    ) -> Session:
        row = Session(
            user_id=user_id,
            refresh_token_family_id=family_id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_label=_label_from_user_agent(user_agent),
            expires_at=expires_at,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def touch_session(self, family_id: uuid.UUID) -> None:
        row = await self.session_repo.get_by_family_id(family_id)
        if row is not None and row.is_active:
            await self.session_repo.touch(row)

    async def list_for_user(self, user_id: uuid.UUID) -> list[Session]:
        return await self.session_repo.list_active_for_user(user_id)

    async def revoke(self, user_id: uuid.UUID, session_id: uuid.UUID) -> uuid.UUID:
        """Revoke one of `user_id`'s own sessions. Returns its `family_id` so
        the caller can also revoke the backing refresh-token family."""
        row = await self.session_repo.get_by_id(session_id)
        if row is None:
            raise NotFoundError("Session not found.")
        if row.user_id != user_id:
            raise ForbiddenError("You may not revoke another user's session.")
        family_id = row.refresh_token_family_id
        await self.session_repo.revoke(row)
        return family_id

    async def revoke_by_family_id(self, user_id: uuid.UUID, family_id: uuid.UUID) -> None:
        row = await self.session_repo.get_by_family_id(family_id)
        if row is not None and row.user_id == user_id and row.is_active:
            await self.session_repo.revoke(row)


def _label_from_user_agent(user_agent: str | None) -> str | None:
    """Best-effort, dependency-free device label — not a full UA parser."""
    if not user_agent:
        return None
    ua = user_agent.lower()

    browser_labels = {"edg": "Edge", "chrome": "Chrome", "firefox": "Firefox", "safari": "Safari"}
    browser = next((label for key, label in browser_labels.items() if key in ua), "Unknown browser")

    os_labels = {
        "windows": "Windows",
        "mac os": "macOS",
        "android": "Android",
        "iphone": "iOS",
        "ipad": "iOS",
        "linux": "Linux",
    }
    os_name = next((label for key, label in os_labels.items() if key in ua), "Unknown OS")

    return f"{browser} on {os_name}"
