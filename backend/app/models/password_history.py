"""PasswordHistory — recent password hashes, so users can't reuse them."""

import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class PasswordHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Stores past bcrypt hashes (never plaintext) for a user, so
    `PasswordService.validate_not_reused` can reject a new password that
    matches one of the last N. Pruned to the most recent N rows by
    `PasswordService` after every successful change — see
    `docs/security.md` for the policy.
    """

    __tablename__ = "password_history"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(60), nullable=False)
