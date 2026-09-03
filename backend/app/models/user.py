"""User identity model — the authentication/authorization principal."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.utils.datetime_utils import ensure_aware

if TYPE_CHECKING:
    from app.models.refresh_token import RefreshToken
    from app.models.session import Session
    from app.models.user_role import UserRole


class User(UUIDPrimaryKeyMixin, TimestampMixin, AuditActorMixin, SoftDeleteMixin, Base):
    """
    A platform user (any role — Super Admin, Institution Admin, Teacher,
    or Student). Role/permission assignment lives in `UserRole` /
    `RolePermission`, not on this model, so a user's authorization can
    change without altering identity data.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(60), nullable=False)

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user",
        foreign_keys="UserRole.user_id",
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        foreign_keys="RefreshToken.user_id",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user",
        foreign_keys="Session.user_id",
        cascade="all, delete-orphan",
    )

    @property
    def is_locked(self) -> bool:
        """True while an account-lockout window (set by AuthService) is active."""
        if self.locked_until is None:
            return False
        return ensure_aware(self.locked_until) > datetime.now(UTC)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<User id={self.id} username={self.username!r}>"
