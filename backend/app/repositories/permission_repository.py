"""Persistence access for `Permission`."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.permission import Permission
from app.repositories.base import BaseRepository


class PermissionRepository(BaseRepository[Permission]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Permission, session)

    async def get_by_code(self, code: str) -> Permission | None:
        result = await self.session.execute(select(Permission).where(Permission.code == code))
        return result.scalar_one_or_none()

    async def list_all(self, *, limit: int = 2000, offset: int = 0) -> list[Permission]:
        # Default bumped from 200 (Module 02) to 2000 (Module 04): the
        # `/permissions` endpoint's contract is "list all" with no exposed
        # pagination params, so this cap must comfortably exceed the total
        # `PermissionCode` count as more domains add their own codes — 200
        # silently truncated results once Module 04 pushed the real count
        # past it (a critical, discovered-in-testing bug, not a style
        # choice — see `test_rbac.py::test_super_admin_role_includes_every_permission`).
        result = await self.session.execute(
            select(Permission)
            .order_by(Permission.resource, Permission.action)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
