"""Permission model — an atomic, role-independent capability."""

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.role_permission import RolePermission


class Permission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    An atomic capability, e.g. `users:create` or `sessions:revoke`.

    Deliberately independent of `Role`: permissions are the unit of
    authorization, roles are just a convenient way to grant a bundle of
    them to a user at once (via `RolePermission`). This is what lets a
    future policy engine (or a per-user permission override) sit alongside
    roles without a redesign — see `docs/rbac.md`.

    `code` follows a `resource:action` convention (enforced by
    `PermissionRepository.seed_defaults`, not a DB constraint, so it stays
    easy to extend).
    """

    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    resource: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    role_permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="permission", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Permission id={self.id} code={self.code!r}>"
