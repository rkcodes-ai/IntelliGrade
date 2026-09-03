"""PasswordResetToken — single-use, short-lived token backing the forgot-password flow."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.utils.datetime_utils import ensure_aware


class PasswordResetToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One row per issued password-reset token. Like `RefreshToken`, only a
    SHA-256 hash of the raw token is stored. `used_at` is set the moment
    the token is redeemed so it can never be replayed, independent of
    `expires_at`.

    Delivery (emailing the raw token to the user) is out of scope for this
    module — see `docs/authentication-guide.md` for how this integrates
    with the future Notification module.
    """

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and ensure_aware(self.expires_at) > datetime.now(UTC)
