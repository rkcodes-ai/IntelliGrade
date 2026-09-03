"""
RBAC (Role-Based Access Control) dependency layer.

`get_current_user` decodes the bearer access token, loads the user (with
roles and each role's permissions eagerly joined in one query via
`UserRepository`) from the database, and rejects missing/expired/malformed
tokens and inactive accounts. `require_roles` / `require_permissions` build
on top of it for endpoint-level authorization.

Roles and permissions are deliberately checked as plain strings, not the
`Role` enum: `Role` members are `StrEnum` (so `Role.TEACHER` already *is*
the string `"teacher"` and works everywhere a string does), but a role
created later at runtime — with no corresponding enum member — must
authorize identically. See `docs/rbac.md`.
"""

import uuid
from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.user_repository import UserRepository

_bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")


class CurrentUser:
    """
    The authenticated principal for the current request.

    Wraps the ORM `User` and precomputes role/permission sets once per
    request (not once per `require_roles`/`require_permissions` check —
    an endpoint with several authorization dependencies shouldn't re-walk
    the relationship graph for each one).
    """

    def __init__(self, user: User, session_family_id: uuid.UUID | None = None) -> None:
        self.user = user
        self.id: uuid.UUID = user.id
        self.session_family_id = session_family_id
        self.role_names: frozenset[str] = frozenset(ur.role.name for ur in user.user_roles)
        self.permissions: frozenset[str] = frozenset(
            role_permission.permission.code
            for user_role in user.user_roles
            for role_permission in user_role.role.role_permissions
        )

    def has_role(self, *role_names: str) -> bool:
        return bool(self.role_names.intersection(role_names))

    def has_permission(self, *permission_codes: str) -> bool:
        return set(permission_codes).issubset(self.permissions)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> CurrentUser:
    """
    Resolve the authenticated user from the `Authorization: Bearer <token>`
    header. Raises `UnauthorizedError` (401) for anything wrong with the
    token or the account it names — never a generic 500, so clients can
    reliably distinguish "log in again" from "something broke."
    """
    if credentials is None:
        raise UnauthorizedError("Not authenticated.")

    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Access token has expired.") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid access token.") from exc

    if payload.get("type") != "access":
        raise UnauthorizedError("Token is not an access token.")

    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except ValueError as exc:
        raise UnauthorizedError("Malformed access token.") from exc

    user = await UserRepository(db).get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("User account no longer exists.")
    if not user.is_active:
        raise UnauthorizedError("This account has been deactivated.")

    session_family_id: uuid.UUID | None = None
    if "family_id" in payload:
        try:
            session_family_id = uuid.UUID(str(payload["family_id"]))
        except ValueError:
            session_family_id = None

    current_user = CurrentUser(user, session_family_id)
    request.state.user = current_user
    return current_user


def require_roles(*allowed_roles: str) -> Callable[..., CurrentUser]:
    """
    Dependency factory restricting an endpoint to a set of roles.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_roles(Role.SUPER_ADMIN))])
    """
    allowed = frozenset(allowed_roles)

    def dependency(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if not current_user.has_role(*allowed):
            raise ForbiddenError("You do not have the required role for this action.")
        return current_user

    return dependency


def require_permissions(*required_permissions: str) -> Callable[..., CurrentUser]:
    """
    Dependency factory restricting an endpoint to callers holding *all* of
    the given permissions (via any of their assigned roles). Prefer this
    over `require_roles` for most endpoints — it keeps authorization
    correct even if role→permission grants change later, since the
    endpoint never hardcodes a role name.

    Usage:
        @router.post(
            "/users", dependencies=[Depends(require_permissions(PermissionCode.USERS_CREATE))]
        )
    """
    required = frozenset(required_permissions)

    def dependency(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if not current_user.has_permission(*required):
            raise ForbiddenError("You do not have permission to perform this action.")
        return current_user

    return dependency
