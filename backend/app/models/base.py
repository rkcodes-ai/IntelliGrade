"""
Reusable model mixins.

Not business tables themselves — these mixins exist so every domain model
(User, Role, RefreshToken, ...) gets a consistent primary key, audit trail,
and soft-delete behavior without duplicating column definitions.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKeyMixin:
    """
    Adds a UUID primary key column named `id`.

    Uses SQLAlchemy's dialect-agnostic `Uuid` type rather than
    `postgresql.UUID` directly: it still renders as PostgreSQL's native
    `UUID` column in production (verified: identical DDL), but also works
    against SQLite, which the test suite uses for fast, isolated
    integration tests (see `backend/tests/conftest.py`). Generation stays
    application-side via `uuid.uuid4()` — see ADR-002 in
    `ARCHITECTURE_DECISIONS.md`.
    """

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """Adds `created_at` / `updated_at` audit columns, managed by the database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AuditActorMixin:
    """
    Adds `created_by` / `updated_by` — who performed the write, not just when.

    Nullable and *not* a hard foreign key to `users.id`: the very first user
    in a fresh database (bootstrap super admin) has no creator, and system/
    migration-seeded rows have no human actor at all. Application code sets
    these from the authenticated principal when available.
    """

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class SoftDeleteMixin:
    """
    Adds `deleted_at` for soft deletion — rows are never physically removed.

    `is_deleted` is a Python-side convenience property, not a query filter:
    repositories are responsible for filtering `deleted_at IS NULL` in their
    queries (see `app/repositories/user_repository.py`).
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def mark_deleted(self) -> None:
        self.deleted_at = datetime.now(UTC)

    def restore(self) -> None:
        self.deleted_at = None
