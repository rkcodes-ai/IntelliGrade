"""Role model — a named, assignable bundle of permissions."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.role_permission import RolePermission
    from app.models.user_role import UserRole


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A named role (e.g. `super_admin`, `teacher`). Authorization decisions
    are driven by the permissions attached via `RolePermission`, not by the
    role name itself — the name is a human-friendly label and a stable
    handle for seed data, not a hardcoded authorization switch. New roles
    can be added at runtime without a code change.
    """

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # System roles (the four canonical ones seeded by migration) can't be
    # deleted or renamed via the API — see RBACService.delete_role.
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    role_permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )
    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Role id={self.id} name={self.name!r}>"
