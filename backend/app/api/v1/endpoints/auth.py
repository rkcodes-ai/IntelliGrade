"""
Authentication endpoints: login, logout, refresh, and the
forgot/reset/change password flows.

The refresh token is never exposed in a JSON body — it's set as an
httpOnly, SameSite=Lax cookie scoped to `/api/v1/auth` (see
`Settings.REFRESH_TOKEN_COOKIE_PATH`), so client-side JavaScript can never
read or exfiltrate it. See `docs/authentication-guide.md` for the full
cookie/CSRF posture.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.middleware.rate_limit import limiter
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.user import UserRead
from app.services.auth_service import AuthService, RequestContext
from app.services.rbac_service import RBACService

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _request_context(request: Request) -> RequestContext:
    return RequestContext(
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        request_id=getattr(request.state, "request_id", None),
    )


def _set_refresh_cookie(response: Response, raw_refresh_token: str, expires_at: datetime) -> None:
    max_age = max(int((expires_at - datetime.now(UTC)).total_seconds()), 0)
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=raw_refresh_token,
        max_age=max_age,
        path=settings.REFRESH_TOKEN_COOKIE_PATH,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        path=settings.REFRESH_TOKEN_COOKIE_PATH,
    )


def _user_to_read(user: User) -> UserRead:
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


@router.post("/login", response_model=TokenResponse, summary="Authenticate and receive tokens")
@limiter.limit("10/minute")
async def login(
    request: Request, response: Response, body: LoginRequest, db: DbSession
) -> TokenResponse:
    service = AuthService(db)
    token_pair, user = await service.login(
        body.identifier, body.password, remember_me=body.remember_me, ctx=_request_context(request)
    )
    await db.commit()

    _set_refresh_cookie(response, token_pair.refresh_token, token_pair.refresh_token_expires_at)
    return TokenResponse(
        access_token=token_pair.access_token,
        expires_in=token_pair.access_token_expires_in,
        user=_user_to_read(user),
    )


@router.post("/logout", response_model=MessageResponse, summary="Revoke the current session")
async def logout(request: Request, response: Response, db: DbSession) -> MessageResponse:
    raw_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if raw_token:
        service = AuthService(db)
        await service.logout(raw_token, _request_context(request))
        await db.commit()
    _clear_refresh_cookie(response)
    return MessageResponse(message="Logged out.")


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate the refresh token, issue a new access token",
)
async def refresh(request: Request, response: Response, db: DbSession) -> TokenResponse:
    raw_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if not raw_token:
        raise UnauthorizedError("No refresh token presented.")

    service = AuthService(db)
    token_pair, user = await service.refresh(raw_token, _request_context(request))
    await db.commit()

    _set_refresh_cookie(response, token_pair.refresh_token, token_pair.refresh_token_expires_at)
    return TokenResponse(
        access_token=token_pair.access_token,
        expires_in=token_pair.access_token_expires_in,
        user=_user_to_read(user),
    )


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a password reset link",
)
@limiter.limit("5/minute")
async def forgot_password(
    request: Request, body: ForgotPasswordRequest, db: DbSession
) -> MessageResponse:
    service = AuthService(db)
    await service.request_password_reset(body.email, _request_context(request))
    await db.commit()
    # Always the same response, whether or not the email is registered —
    # see AuthService.request_password_reset.
    return MessageResponse(message="If that email is registered, a reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse, summary="Complete a password reset")
async def reset_password(
    request: Request, body: ResetPasswordRequest, db: DbSession
) -> MessageResponse:
    service = AuthService(db)
    await service.reset_password(body.token, body.new_password, _request_context(request))
    await db.commit()
    return MessageResponse(message="Password has been reset. Please log in again.")


@router.post("/change-password", response_model=MessageResponse, summary="Change your own password")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    db: DbSession,
    current_user: CurrentUserDep,
) -> MessageResponse:
    service = AuthService(db)
    await service.change_password(
        current_user.user, body.current_password, body.new_password, _request_context(request)
    )
    await db.commit()
    return MessageResponse(message="Password changed. Other sessions have been signed out.")
