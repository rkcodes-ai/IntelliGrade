"""AuditLog — immutable record of security-relevant events."""

import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One row per security-relevant event (login, logout, failed login,
    password change, role change, session revocation, ...). Written by
    `AuditService` and never updated or deleted by application code — an
    audit trail that can be edited after the fact isn't one.

    `user_id` is nullable: a failed login with an unrecognized username has
    no user to attribute it to, but the attempt itself must still be
    logged (see `docs/security.md`).
    """

    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # "success" | "failure"

    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
