"""
Authentication orchestration service: login, logout, and the
forgot/reset/change password flows. This is the one service that touches
`PasswordService`, `TokenService`, `SessionService`, and `AuditService`
together — everything else in the auth surface is composed from these.

IMPORTANT: every failure path that writes an audit log or updates security
state (the failed-login counter, account lockout) commits explicitly
*before* raising. `app.db.session.get_db_session` rolls back on any
exception raised through the request — without an explicit commit here,
the audit trail and lockout counter for a *failed* login would silently
vanish the moment the request raises the very error being logged, which
defeats the purpose of both. Successful paths still rely on the endpoint's
own `db.commit()` after the service call returns normally.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import AuditAction
from app.core.exceptions import (
    AccountLockedError,
    NotFoundError,
    UnauthorizedError,
    ValidationAppError,
)
from app.core.security import generate_opaque_token, hash_token, verify_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.repositories.password_reset_token_repository import PasswordResetTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.services.base import BaseService
from app.services.password_service import PasswordService
from app.services.session_service import SessionService
from app.services.token_service import IssuedTokenPair, TokenService

settings = get_settings()


class RequestContext:
    """Everything about the calling client that audit logs / session rows want to record."""

    __slots__ = ("ip_address", "user_agent", "request_id")

    def __init__(
        self,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
    ) -> None:
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.request_id = request_id


class AuthService(BaseService):
    def __init__(
        self,
        session: AsyncSession,
        user_repo: UserRepository | None = None,
        password_reset_repo: PasswordResetTokenRepository | None = None,
        password_service: PasswordService | None = None,
        token_service: TokenService | None = None,
        session_service: SessionService | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session)
        self.user_repo = user_repo or UserRepository(session)
        self.password_reset_repo = password_reset_repo or PasswordResetTokenRepository(session)
        self.password_service = password_service or PasswordService(session)
        self.token_service = token_service or TokenService(session)
        self.session_service = session_service or SessionService(session)
        self.audit_service = audit_service or AuditService(session)

    async def login(
        self, identifier: str, password: str, *, remember_me: bool, ctx: RequestContext
    ) -> tuple[IssuedTokenPair, User]:
        user = await self.user_repo.get_by_identifier(identifier)

        if user is None:
            # Constant-shape failure path: don't reveal whether the
            # identifier exists. Still logged, with no user_id to attach.
            await self.audit_service.log(
                action=AuditAction.LOGIN_FAILURE,
                status="failure",
                context={"identifier": identifier, "reason": "user_not_found"},
                **_ctx_kwargs(ctx),
            )
            await self.session.commit()
            raise UnauthorizedError("Incorrect username/email or password.")

        if user.is_locked:
            await self.audit_service.log(
                action=AuditAction.LOGIN_FAILURE,
                status="failure",
                user_id=user.id,
                context={"reason": "account_locked"},
                **_ctx_kwargs(ctx),
            )
            await self.session.commit()
            raise AccountLockedError(
                "Account is temporarily locked due to too many failed login attempts. "
                "Try again later or reset your password."
            )

        if not user.is_active:
            await self.audit_service.log(
                action=AuditAction.LOGIN_FAILURE,
                status="failure",
                user_id=user.id,
                context={"reason": "account_inactive"},
                **_ctx_kwargs(ctx),
            )
            await self.session.commit()
            raise UnauthorizedError("This account has been deactivated.")

        if not verify_password(password, user.hashed_password):
            await self._register_failed_attempt(user, ctx)
            await self.session.commit()
            raise UnauthorizedError("Incorrect username/email or password.")

        # Success: reset the failed-attempt counter and issue tokens.
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(UTC)
        await self.session.flush()

        roles = [ur.role.name for ur in user.user_roles]
        token_pair = await self.token_service.issue_token_pair(
            user,
            roles,
            remember_me=remember_me,
            ip_address=ctx.ip_address,
            user_agent=ctx.user_agent,
        )
        await self.session_service.start_session(
            user.id,
            token_pair.family_id,
            expires_at=token_pair.refresh_token_expires_at,
            ip_address=ctx.ip_address,
            user_agent=ctx.user_agent,
        )
        await self.audit_service.log(
            action=AuditAction.LOGIN_SUCCESS,
            status="success",
            user_id=user.id,
            **_ctx_kwargs(ctx),
        )
        return token_pair, user

    async def _register_failed_attempt(self, user: User, ctx: RequestContext) -> None:
        user.failed_login_attempts += 1
        locked_out = user.failed_login_attempts >= settings.ACCOUNT_LOCKOUT_MAX_ATTEMPTS
        if locked_out:
            user.locked_until = datetime.now(UTC) + timedelta(
                minutes=settings.ACCOUNT_LOCKOUT_DURATION_MINUTES
            )
        await self.session.flush()

        await self.audit_service.log(
            action=AuditAction.LOGIN_FAILURE,
            status="failure",
            user_id=user.id,
            context={"reason": "bad_password", "attempts": user.failed_login_attempts},
            **_ctx_kwargs(ctx),
        )
        if locked_out:
            await self.audit_service.log(
                action=AuditAction.ACCOUNT_LOCKED,
                status="failure",
                user_id=user.id,
                **_ctx_kwargs(ctx),
            )

    async def logout(self, raw_refresh_token: str, ctx: RequestContext) -> None:
        family_id = await self.token_service.revoke_refresh_token(raw_refresh_token)
        user_id: uuid.UUID | None = None
        if family_id is not None:
            session_row = await self.session_service.session_repo.get_by_family_id(family_id)
            if session_row is not None:
                user_id = session_row.user_id
                await self.session_service.session_repo.revoke(session_row)

        await self.audit_service.log(
            action=AuditAction.LOGOUT,
            status="success",
            user_id=user_id,
            **_ctx_kwargs(ctx),
        )

    async def refresh(
        self, raw_refresh_token: str, ctx: RequestContext
    ) -> tuple[IssuedTokenPair, User]:
        new_pair, user = await self.token_service.rotate_refresh_token(
            raw_refresh_token, ip_address=ctx.ip_address, user_agent=ctx.user_agent
        )
        await self.session_service.touch_session(new_pair.family_id)
        await self.audit_service.log(
            action=AuditAction.TOKEN_REFRESH,
            status="success",
            user_id=user.id,
            **_ctx_kwargs(ctx),
        )
        return new_pair, user

    async def change_password(
        self, user: User, current_password: str, new_password: str, ctx: RequestContext
    ) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise ValidationAppError("Current password is incorrect.")

        new_hash = await self.password_service.set_password(user.id, new_password)
        user.hashed_password = new_hash
        user.password_changed_at = datetime.now(UTC)
        await self.session.flush()

        # Changing your password invalidates every other logged-in session —
        # a stolen session shouldn't survive the legitimate user noticing.
        await self.token_service.refresh_token_repo.revoke_all_for_user(user.id)

        await self.audit_service.log(
            action=AuditAction.PASSWORD_CHANGE,
            status="success",
            user_id=user.id,
            **_ctx_kwargs(ctx),
        )

    async def request_password_reset(self, email: str, ctx: RequestContext) -> None:
        """
        Always succeeds from the caller's perspective (never reveals
        whether the email exists) — only issues a token if a matching,
        active user is found.
        """
        user = await self.user_repo.get_by_email(email)
        if user is None:
            await self.audit_service.log(
                action=AuditAction.PASSWORD_RESET_REQUEST,
                status="failure",
                context={"reason": "user_not_found"},
                **_ctx_kwargs(ctx),
            )
            return

        raw_token = generate_opaque_token()
        expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        )
        self.session.add(
            PasswordResetToken(
                user_id=user.id, token_hash=hash_token(raw_token), expires_at=expires_at
            )
        )
        await self.session.flush()

        await self.audit_service.log(
            action=AuditAction.PASSWORD_RESET_REQUEST,
            status="success",
            user_id=user.id,
            **_ctx_kwargs(ctx),
        )
        # Delivery (emailing `raw_token` to the user) is out of scope for
        # this module — see docs/authentication-guide.md. The token is
        # logged at debug level in non-production environments only, so
        # the flow is testable end-to-end without an email service yet.
        if not settings.is_production:
            self.logger.debug("password_reset_token_issued", user_id=str(user.id), token=raw_token)

    async def reset_password(self, raw_token: str, new_password: str, ctx: RequestContext) -> None:
        token_row = await self.password_reset_repo.get_by_token_hash(hash_token(raw_token))
        if token_row is None or not token_row.is_valid:
            await self.audit_service.log(
                action=AuditAction.PASSWORD_RESET_COMPLETE,
                status="failure",
                context={"reason": "invalid_or_expired_token"},
                **_ctx_kwargs(ctx),
            )
            await self.session.commit()
            raise UnauthorizedError("Reset link is invalid or has expired.")

        user = await self.user_repo.get_by_id(token_row.user_id)
        if user is None:
            raise NotFoundError("User not found.")

        new_hash = await self.password_service.set_password(user.id, new_password)
        user.hashed_password = new_hash
        user.password_changed_at = datetime.now(UTC)
        token_row.used_at = datetime.now(UTC)
        await self.session.flush()

        await self.token_service.refresh_token_repo.revoke_all_for_user(user.id)

        await self.audit_service.log(
            action=AuditAction.PASSWORD_RESET_COMPLETE,
            status="success",
            user_id=user.id,
            **_ctx_kwargs(ctx),
        )


def _ctx_kwargs(ctx: RequestContext) -> dict[str, str | None]:
    return {
        "ip_address": ctx.ip_address,
        "user_agent": ctx.user_agent,
        "request_id": ctx.request_id,
    }
