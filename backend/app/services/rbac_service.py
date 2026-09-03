"""
Authorization service: role assignment and effective-permission computation.

`app.core.rbac` (the FastAPI dependency layer) calls into this service to
resolve "what can this user do," but owns none of the DB access itself —
keeping the dependency layer thin and this service unit-testable without
spinning up a request.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.role import Role
from app.models.user import User
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.services.base import BaseService


class RBACService(BaseService):
    def __init__(
        self,
        session: AsyncSession,
        role_repo: RoleRepository | None = None,
        user_repo: UserRepository | None = None,
    ) -> None:
        super().__init__(session)
        self.role_repo = role_repo or RoleRepository(session)
        self.user_repo = user_repo or UserRepository(session)

    @staticmethod
    def role_names(user: User) -> list[str]:
        return [ur.role.name for ur in user.user_roles]

    @staticmethod
    def effective_permissions(user: User) -> set[str]:
        """Union of every permission granted by every role the user holds."""
        permissions: set[str] = set()
        for user_role in user.user_roles:
            for role_permission in user_role.role.role_permissions:
                permissions.add(role_permission.permission.code)
        return permissions

    async def list_roles(self) -> list[Role]:
        return await self.role_repo.list_all()

    async def assign_role(
        self, user_id: uuid.UUID, role_name: str, *, assigned_by: uuid.UUID | None
    ) -> None:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        role = await self.role_repo.get_by_name(role_name)
        if role is None:
            raise NotFoundError(f"Role '{role_name}' not found.")
        if role.name in self.role_names(user):
            raise ConflictError(f"User already has role '{role_name}'.")

        await self.user_repo.add_role(user, role, assigned_by=assigned_by)

    async def revoke_role(self, user_id: uuid.UUID, role_name: str) -> None:
        role = await self.role_repo.get_by_name(role_name)
        if role is None:
            raise NotFoundError(f"Role '{role_name}' not found.")
        removed = await self.user_repo.remove_role(user_id, role.id)
        if not removed:
            raise NotFoundError("User does not have that role.")
