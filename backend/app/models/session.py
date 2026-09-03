"""Session — a user-visible record of one logged-in device/browser."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class Session(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A logical login session, one per successful `/auth/login` (distinct
    from `RefreshToken`, which tracks the rotation chain — a session
    survives multiple token rotations for as long as the user stays logged
    in on that device). This is what the "Session Management UI" and
    `GET/DELETE /sessions` endpoints operate on: a user recognizes "Chrome
    on Windows, last active 2 minutes ago," not a raw token.
    """

    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    refresh_token_family_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    device_label: Mapped[str | None] = mapped_column(String(200), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions", foreign_keys=[user_id])
