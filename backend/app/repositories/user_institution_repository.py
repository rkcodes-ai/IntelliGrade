"""Persistence access for `UserInstitution` (tenant membership)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_institution import UserInstitution
from app.repositories.base import BaseRepository


class UserInstitutionRepository(BaseRepository[UserInstitution]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(UserInstitution, session)

    async def get_membership(
        self, user_id: uuid.UUID, institution_id: uuid.UUID
    ) -> UserInstitution | None:
        result = await self.session.execute(
            select(UserInstitution).where(
                UserInstitution.user_id == user_id,
                UserInstitution.institution_id == institution_id,
                UserInstitution.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[UserInstitution]:
        result = await self.session.execute(
            select(UserInstitution).where(
                UserInstitution.user_id == user_id, UserInstitution.is_active.is_(True)
            )
        )
        return list(result.scalars().all())

    async def list_for_institution(self, institution_id: uuid.UUID) -> list[UserInstitution]:
        result = await self.session.execute(
            select(UserInstitution).where(
                UserInstitution.institution_id == institution_id,
                UserInstitution.is_active.is_(True),
            )
        )
        return list(result.scalars().all())
