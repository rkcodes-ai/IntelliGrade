"""Persistence access for `User`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User
from app.models.user_role import UserRole
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """
    All read queries here filter out soft-deleted rows (`deleted_at IS
    NULL`) by default — a deleted user must not be findable by login,
    email/username lookup, or listing, even though the row still exists
    for audit purposes. `get_by_id_include_deleted` is the one deliberate
    exception, used only by admin "restore" tooling.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    def _with_roles(self):
        # Eager-loads the full chain user -> user_roles -> role ->
        # role_permissions -> permission in one query. Required, not just
        # an optimization: `app.core.rbac.CurrentUser` computes the user's
        # effective permission set synchronously from these relationships,
        # and a lazy load there (outside the async session's greenlet
        # context by the time it's accessed) raises `MissingGreenlet`
        # rather than quietly falling back to a blocking query.
        return select(User).options(
            selectinload(User.user_roles)
            .selectinload(UserRole.role)
            .selectinload(Role.role_permissions)
            .selectinload(RolePermission.permission)
        )

    async def get_by_id(self, entity_id: uuid.UUID) -> User | None:
        result = await self.session.execute(
            self._with_roles().where(User.id == entity_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_id_include_deleted(self, entity_id: uuid.UUID) -> User | None:
        result = await self.session.execute(self._with_roles().where(User.id == entity_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            self._with_roles().where(User.email == email.lower(), User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(
            self._with_roles().where(User.username == username, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_identifier(self, identifier: str) -> User | None:
        """Look up by username OR email — used at login, where either is accepted."""
        if "@" in identifier:
            return await self.get_by_email(identifier)
        return await self.get_by_username(identifier)

    async def email_exists(self, email: str) -> bool:
        result = await self.session.execute(select(User.id).where(User.email == email.lower()))
        return result.scalar_one_or_none() is not None

    async def username_exists(self, username: str) -> bool:
        result = await self.session.execute(select(User.id).where(User.username == username))
        return result.scalar_one_or_none() is not None

    async def list_active(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        result = await self.session.execute(
            self._with_roles()
            .where(User.deleted_at.is_(None))
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def add_role(self, user: User, role: Role, *, assigned_by: uuid.UUID | None) -> UserRole:
        user_role = UserRole(user_id=user.id, role_id=role.id, assigned_by=assigned_by)
        self.session.add(user_role)
        await self.session.flush()
        return user_role

    async def remove_role(self, user_id: uuid.UUID, role_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
        )
        user_role = result.scalar_one_or_none()
        if user_role is None:
            return False
        await self.session.delete(user_role)
        await self.session.flush()
        return True
