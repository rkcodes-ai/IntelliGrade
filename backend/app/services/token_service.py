"""
Token lifecycle service: access-token issuance and refresh-token rotation.

Refresh token rotation strategy (OWASP-recommended pattern):

1. Login issues an access token (short-lived JWT, not persisted) and a
   refresh token (JWT with a `jti`, persisted as a `RefreshToken` row
   keyed by a hash of the token, never the raw value).
2. Every refresh token belongs to a `family_id`, shared across the whole
   chain of rotations that trace back to one login.
3. `/auth/refresh` looks up the presented token by hash:
   - Not found / expired / already revoked *and not reused-detectable* →
     reject (`UnauthorizedError`).
   - Found, active, not expired → rotate: revoke it (`replaced_by_id` set),
     issue a new access + refresh token pair in the same family.
   - Found but **already revoked** → this is a replay of a stale token
     after the legitimate client already rotated past it — the strongest
     available signal that the token was stolen. The entire family is
     revoked, forcing re-authentication everywhere. See
     `docs/authentication-guide.md`.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import AuditAction
from app.core.exceptions import UnauthorizedError
from app.core.security import create_token, decode_token, generate_jti, hash_token
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.services.base import BaseService

settings = get_settings()


class IssuedTokenPair:
    """Return shape for a freshly issued access + refresh token pair."""

    __slots__ = (
        "access_token",
        "refresh_token",
        "refresh_token_expires_at",
        "family_id",
        "access_token_expires_in",
    )

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        refresh_token_expires_at: datetime,
        family_id: uuid.UUID,
    ) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.refresh_token_expires_at = refresh_token_expires_at
        self.family_id = family_id
        self.access_token_expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


class TokenService(BaseService):
    def __init__(
        self,
        session: AsyncSession,
        refresh_token_repo: RefreshTokenRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session)
        self.refresh_token_repo = refresh_token_repo or RefreshTokenRepository(session)
        self.audit_service = audit_service or AuditService(session)

    def create_access_token(
        self, user: User, roles: list[str], *, family_id: uuid.UUID | None = None
    ) -> str:
        # `family_id` rides on the access token too (not just the refresh
        # token), because the refresh-token cookie is intentionally scoped
        # to `Settings.REFRESH_TOKEN_COOKIE_PATH` (only sent on auth
        # endpoints) — endpoints like GET /sessions need a way to identify
        # "which session is this request using" without that cookie, and
        # the Authorization header is present on every authenticated
        # request regardless of cookie path scoping.
        claims: dict[str, str] = {"jti": generate_jti()}
        if family_id is not None:
            claims["family_id"] = str(family_id)
        return create_token(
            subject=str(user.id),
            token_type="access",
            extra_claims={"roles": roles, **claims},
        )

    async def issue_token_pair(
        self,
        user: User,
        roles: list[str],
        *,
        remember_me: bool = False,
        ip_address: str | None = None,
        user_agent: str | None = None,
        family_id: uuid.UUID | None = None,
    ) -> IssuedTokenPair:
        """
        Issue a fresh access+refresh pair. `family_id` is omitted on a new
        login (a new family is started) and passed explicitly during
        rotation (the new token joins the existing family).
        """
        family_id = family_id or uuid.uuid4()
        jti = generate_jti()
        expire_days = (
            settings.REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS
            if remember_me
            else settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        expires_at = datetime.now(UTC) + timedelta(days=expire_days)

        refresh_jwt = create_token(
            subject=str(user.id),
            token_type="refresh",
            extra_claims={"jti": jti, "family_id": str(family_id)},
        )

        access_token = self.create_access_token(user, roles, family_id=family_id)

        row = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_jwt),
            family_id=family_id,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.add(row)
        await self.session.flush()

        return IssuedTokenPair(access_token, refresh_jwt, expires_at, family_id)

    async def rotate_refresh_token(
        self,
        raw_refresh_token: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[IssuedTokenPair, User]:
        """
        Validate and rotate a presented refresh token. Raises
        `UnauthorizedError` for any invalid/expired/revoked token. On reuse
        detection, revokes the whole family before raising.
        """
        try:
            payload = decode_token(raw_refresh_token)
        except Exception as exc:
            raise UnauthorizedError("Invalid or expired refresh token.") from exc

        if payload.get("type") != "refresh":
            raise UnauthorizedError("Token is not a refresh token.")

        token_hash = hash_token(raw_refresh_token)
        existing = await self.refresh_token_repo.get_by_token_hash(token_hash)
        if existing is None:
            raise UnauthorizedError("Refresh token not recognized.")

        if existing.revoked_at is not None:
            # Reuse of an already-rotated token: treat the family as compromised.
            # Committed immediately (not left to the caller) — this security
            # response must survive even though the request as a whole errors
            # out; see the note in app.services.auth_service on this pattern.
            await self.refresh_token_repo.revoke_family(existing.family_id)
            await self.audit_service.log(
                action=AuditAction.TOKEN_REUSE_DETECTED,
                status="failure",
                user_id=existing.user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                context={"family_id": str(existing.family_id)},
            )
            await self.session.commit()
            raise UnauthorizedError("Refresh token has already been used. All sessions revoked.")

        if not existing.is_active:
            raise UnauthorizedError("Refresh token has expired.")

        user = await UserRepository(self.session).get_by_id(existing.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("User account is no longer active.")

        roles = [ur.role.name for ur in user.user_roles]
        new_pair = await self.issue_token_pair(
            user,
            roles,
            ip_address=ip_address,
            user_agent=user_agent,
            family_id=existing.family_id,
        )
        new_row = await self.refresh_token_repo.get_by_token_hash(
            hash_token(new_pair.refresh_token)
        )
        await self.refresh_token_repo.revoke(
            existing, replaced_by_id=new_row.id if new_row else None
        )

        return new_pair, user

    async def revoke_refresh_token(self, raw_refresh_token: str) -> uuid.UUID | None:
        """Revoke a single refresh token (logout). Returns its family_id, if found."""
        token_hash = hash_token(raw_refresh_token)
        existing = await self.refresh_token_repo.get_by_token_hash(token_hash)
        if existing is None:
            return None
        await self.refresh_token_repo.revoke(existing)
        return existing.family_id
