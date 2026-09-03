"""User management service: admin CRUD + self-service profile updates."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.security import hash_password
from app.models.user import User
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserProfileUpdate, UserUpdate
from app.services.audit_service import AuditService
from app.services.base import BaseService
from app.services.password_service import PasswordService


class UserService(BaseService):
    def __init__(
        self,
        session: AsyncSession,
        user_repo: UserRepository | None = None,
        role_repo: RoleRepository | None = None,
        password_service: PasswordService | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session)
        self.user_repo = user_repo or UserRepository(session)
        self.role_repo = role_repo or RoleRepository(session)
        self.password_service = password_service or PasswordService(session)
        self.audit_service = audit_service or AuditService(session)

    async def get_by_id(self, user_id: uuid.UUID) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    async def list_users(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        return await self.user_repo.list_active(limit=limit, offset=offset)

    async def create_user(
        self,
        data: UserCreate,
        *,
        created_by: uuid.UUID | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
    ) -> User:
        email = data.email.lower()
        if await self.user_repo.email_exists(email):
            raise ConflictError("A user with that email already exists.")
        if await self.user_repo.username_exists(data.username):
            raise ConflictError("That username is already taken.")

        self.password_service.assert_strong(data.password)

        user = User(
            email=email,
            username=data.username,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            phone=data.phone,
            timezone=data.timezone,
            language=data.language,
            is_active=True,
            created_by=created_by,
        )
        user = await self.user_repo.add(user)
        await self.password_service.record_initial_password(user.id, user.hashed_password)

        for role_name in data.role_names:
            role = await self.role_repo.get_by_name(role_name)
            if role is None:
                raise ValidationAppError(f"Role '{role_name}' does not exist.")
            await self.user_repo.add_role(user, role, assigned_by=created_by)

        await self.audit_service.log(
            action=AuditAction.USER_CREATED,
            status="success",
            user_id=created_by,
            resource_type="user",
            resource_id=str(user.id),
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
        # Re-fetch with roles eagerly loaded for a consistent return shape.
        return await self.get_by_id(user.id)

    async def update_user(
        self, user_id: uuid.UUID, data: UserUpdate, *, updated_by: uuid.UUID | None
    ) -> User:
        user = await self.get_by_id(user_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        user.updated_by = updated_by
        await self.session.flush()

        await self.audit_service.log(
            action=AuditAction.USER_UPDATED,
            status="success",
            user_id=updated_by,
            resource_type="user",
            resource_id=str(user.id),
        )
        return user

    async def update_own_profile(self, user_id: uuid.UUID, data: UserProfileUpdate) -> User:
        user = await self.get_by_id(user_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        user.updated_by = user_id
        await self.session.flush()

        await self.audit_service.log(
            action=AuditAction.PROFILE_UPDATE,
            status="success",
            user_id=user_id,
            resource_type="user",
            resource_id=str(user_id),
        )
        return user

    async def set_active(
        self, user_id: uuid.UUID, *, is_active: bool, actor_id: uuid.UUID | None
    ) -> User:
        user = await self.get_by_id(user_id)
        user.is_active = is_active
        user.updated_by = actor_id
        await self.session.flush()

        await self.audit_service.log(
            action=AuditAction.USER_ACTIVATED if is_active else AuditAction.USER_DEACTIVATED,
            status="success",
            user_id=actor_id,
            resource_type="user",
            resource_id=str(user.id),
        )
        return user

    async def soft_delete(self, user_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> None:
        user = await self.get_by_id(user_id)
        user.mark_deleted()
        user.is_active = False
        user.updated_by = actor_id
        await self.session.flush()

        await self.audit_service.log(
            action=AuditAction.USER_DELETED,
            status="success",
            user_id=actor_id,
            resource_type="user",
            resource_id=str(user.id),
        )
