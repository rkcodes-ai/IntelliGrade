"""
Password lifecycle service: hashing, strength policy, and reuse prevention.

Sits between `app.core.security`/`app.core.password_policy` (pure
primitives) and `AuthService` (which orchestrates the actual login/reset
flows) — this is the one place that knows *both* the policy rules *and*
how to check them against a specific user's stored history.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ValidationAppError
from app.core.password_policy import validate_password_strength
from app.core.security import hash_password, verify_password
from app.repositories.password_history_repository import PasswordHistoryRepository
from app.services.base import BaseService

settings = get_settings()


class PasswordService(BaseService):
    def __init__(
        self,
        session: AsyncSession,
        password_history_repo: PasswordHistoryRepository | None = None,
    ) -> None:
        super().__init__(session)
        self.password_history_repo = password_history_repo or PasswordHistoryRepository(session)

    def assert_strong(self, password: str) -> None:
        """Raise `ValidationAppError` if `password` fails the strength policy."""
        result = validate_password_strength(password)
        if not result.is_valid:
            raise ValidationAppError(
                "Password does not meet security requirements.", details={"errors": result.errors}
            )

    async def assert_not_reused(self, user_id: uuid.UUID, new_password: str) -> None:
        """Raise `ValidationAppError` if `new_password` matches one of the user's last N."""
        recent = await self.password_history_repo.list_recent(
            user_id, limit=settings.PASSWORD_HISTORY_DEPTH
        )
        for entry in recent:
            if verify_password(new_password, entry.hashed_password):
                depth = settings.PASSWORD_HISTORY_DEPTH
                raise ValidationAppError(
                    f"Password must be different from your last {depth} passwords."
                )

    async def set_password(self, user_id: uuid.UUID, new_password: str) -> str:
        """
        Validate, hash, and record `new_password` in history. Returns the
        new hash — callers are responsible for assigning it to
        `User.hashed_password` and committing (this service doesn't touch
        the `User` row directly, keeping it independent of `UserRepository`).
        """
        self.assert_strong(new_password)
        await self.assert_not_reused(user_id, new_password)
        return await self.record_initial_password(user_id, hash_password(new_password))

    async def record_initial_password(self, user_id: uuid.UUID, hashed_password: str) -> str:
        """
        Record an already-hashed password in history without re-validating
        strength or reuse — used at user-creation time, where the plaintext
        was already checked via `assert_strong` and there's no prior history
        to reuse-check against yet.
        """
        await self.password_history_repo.record(user_id, hashed_password)
        await self.password_history_repo.prune_beyond(user_id, keep=settings.PASSWORD_HISTORY_DEPTH)
        return hashed_password
