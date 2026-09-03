"""Persistence access for `Role` and its permission grants."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Role, session)

    def _with_permissions(self):
        return select(Role).options(
            selectinload(Role.role_permissions).selectinload(RolePermission.permission)
        )

    async def get_by_id(self, entity_id: uuid.UUID) -> Role | None:
        result = await self.session.execute(self._with_permissions().where(Role.id == entity_id))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Role | None:
        result = await self.session.execute(self._with_permissions().where(Role.name == name))
        return result.scalar_one_or_none()

    async def list_all(self, *, limit: int = 100, offset: int = 0) -> list[Role]:
        result = await self.session.execute(
            self._with_permissions().order_by(Role.name).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def grant_permission(self, role: Role, permission: Permission) -> RolePermission:
        grant = RolePermission(role_id=role.id, permission_id=permission.id)
        self.session.add(grant)
        await self.session.flush()
        return grant
