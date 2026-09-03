"""
User management endpoints: self-service profile (`/users/me`) and
admin CRUD (`/users`, `/users/{id}`, ...).

IMPORTANT: `/me` routes are registered before `/{user_id}` routes. FastAPI
matches path segments positionally — a `/users/{user_id}` route registered
first would swallow requests to `/users/me` (attempting, and failing, to
parse "me" as a UUID) before the literal `/users/me` route ever got a
chance to match.
"""

import uuid

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.models.user import User
from app.schemas.role import RoleAssignRequest
from app.schemas.user import UserCreate, UserProfileUpdate, UserRead, UserUpdate
from app.services.rbac_service import RBACService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


def _to_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        phone=user.phone,
        avatar_url=user.avatar_url,
        timezone=user.timezone,
        language=user.language,
        preferences=user.preferences,
        is_active=user.is_active,
        is_verified=user.is_verified,
        roles=RBACService.role_names(user),
        permissions=sorted(RBACService.effective_permissions(user)),
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


# --- Self-service ---


@router.get("/me", response_model=UserRead, summary="Get your own profile")
async def get_me(current_user: CurrentUserDep) -> UserRead:
    return _to_read(current_user.user)


@router.patch("/me", response_model=UserRead, summary="Update your own profile")
async def update_me(
    body: UserProfileUpdate, db: DbSession, current_user: CurrentUserDep
) -> UserRead:
    service = UserService(db)
    user = await service.update_own_profile(current_user.id, body)
    await db.commit()
    return _to_read(user)


# --- Admin CRUD ---


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.USERS_CREATE))],
    summary="Create a user (admin)",
)
async def create_user(
    request: Request, body: UserCreate, db: DbSession, current_user: CurrentUserDep
) -> UserRead:
    service = UserService(db)
    user = await service.create_user(
        body,
        created_by=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    await db.commit()
    return _to_read(user)


@router.get(
    "",
    response_model=list[UserRead],
    dependencies=[Depends(require_permissions(PermissionCode.USERS_LIST))],
    summary="List users (admin)",
)
async def list_users(db: DbSession, limit: int = 100, offset: int = 0) -> list[UserRead]:
    service = UserService(db)
    users = await service.list_users(limit=limit, offset=offset)
    return [_to_read(user) for user in users]


@router.get(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(require_permissions(PermissionCode.USERS_READ))],
    summary="Get a user by ID (admin)",
)
async def get_user(user_id: uuid.UUID, db: DbSession) -> UserRead:
    service = UserService(db)
    user = await service.get_by_id(user_id)
    return _to_read(user)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(require_permissions(PermissionCode.USERS_UPDATE))],
    summary="Update a user (admin)",
)
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, db: DbSession, current_user: CurrentUserDep
) -> UserRead:
    service = UserService(db)
    user = await service.update_user(user_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.USERS_DELETE))],
    summary="Soft-delete a user (admin)",
)
async def delete_user(user_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep) -> None:
    service = UserService(db)
    await service.soft_delete(user_id, actor_id=current_user.id)
    await db.commit()


@router.post(
    "/{user_id}/activate",
    response_model=UserRead,
    dependencies=[Depends(require_permissions(PermissionCode.USERS_ACTIVATE))],
    summary="Reactivate a deactivated user (admin)",
)
async def activate_user(
    user_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep
) -> UserRead:
    service = UserService(db)
    user = await service.set_active(user_id, is_active=True, actor_id=current_user.id)
    await db.commit()
    return _to_read(user)


@router.post(
    "/{user_id}/deactivate",
    response_model=UserRead,
    dependencies=[Depends(require_permissions(PermissionCode.USERS_DEACTIVATE))],
    summary="Deactivate a user (admin)",
)
async def deactivate_user(
    user_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep
) -> UserRead:
    service = UserService(db)
    user = await service.set_active(user_id, is_active=False, actor_id=current_user.id)
    await db.commit()
    return _to_read(user)


@router.post(
    "/{user_id}/roles",
    response_model=UserRead,
    dependencies=[Depends(require_permissions(PermissionCode.ROLES_ASSIGN))],
    summary="Grant a role to a user (admin)",
)
async def assign_role(
    user_id: uuid.UUID, body: RoleAssignRequest, db: DbSession, current_user: CurrentUserDep
) -> UserRead:
    rbac_service = RBACService(db)
    await rbac_service.assign_role(user_id, body.role_name, assigned_by=current_user.id)
    await db.commit()
    user = await UserService(db).get_by_id(user_id)
    return _to_read(user)


@router.delete(
    "/{user_id}/roles/{role_name}",
    response_model=UserRead,
    dependencies=[Depends(require_permissions(PermissionCode.ROLES_ASSIGN))],
    summary="Revoke a role from a user (admin)",
)
async def revoke_role(user_id: uuid.UUID, role_name: str, db: DbSession) -> UserRead:
    rbac_service = RBACService(db)
    await rbac_service.revoke_role(user_id, role_name)
    await db.commit()
    user = await UserService(db).get_by_id(user_id)
    return _to_read(user)
