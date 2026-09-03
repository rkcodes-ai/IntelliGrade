"""RefreshToken — persisted record backing the JWT refresh/rotation flow."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.utils.datetime_utils import ensure_aware

if TYPE_CHECKING:
    from app.models.user import User


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One row per issued refresh token. The raw JWT is never stored — only a
    SHA-256 hash of it (`token_hash`), so a database read can't hand an
    attacker a usable token (same principle as password hashing).

    Rotation: on `/auth/refresh`, the presented token's row is looked up by
    hash, checked for revocation/expiry, then marked `revoked_at` with
    `replaced_by_id` pointing at the newly-issued row — see
    `TokenService.rotate_refresh_token`. `family_id` is shared across an
    entire rotation chain from one login, so reuse of an already-rotated
    (stale) token can be detected and the whole family revoked (a stolen
    refresh token being replayed after the legitimate client already
    rotated it is a strong signal of theft).
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True
    )

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens", foreign_keys=[user_id])

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and ensure_aware(self.expires_at) > datetime.now(UTC)
