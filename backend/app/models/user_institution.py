"""
UserInstitution — tenant membership join table.

Not one of the 20 named academic entities; this is Module 03's own
infrastructure for resolving "which institution(s) does this user belong
to," added because `users` (Module 02) cannot be modified — see ADR-014.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.institution import Institution


class UserInstitution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Grants a user membership in an institution. `app.core.tenancy`
    consults this table (never `rbac.py`) to authorize a caller's
    `X-Institution-Id` header — see ADR-015.
    """

    __tablename__ = "user_institutions"
    __table_args__ = (UniqueConstraint("user_id", "institution_id", name="uq_user_institution"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    institution: Mapped["Institution"] = relationship(back_populates="user_memberships")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserInstitution user_id={self.user_id} institution_id={self.institution_id}>"
