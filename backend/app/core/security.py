"""
Security primitives: password hashing, JWT encode/decode, and opaque
token helpers (JTI generation, token hashing for at-rest storage).

This module intentionally stops at *primitives* — no DB access, no request
handling. `app.services.token_service` and `app.services.password_service`
build the actual authentication flows on top of these.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()

TokenType = Literal["access", "refresh"]

# bcrypt hashes only the first 72 bytes of input — passwords longer than that
# are rejected outright rather than silently truncated (silent truncation is
# a security footgun: two different passwords sharing a 72-byte prefix would
# hash identically). The future Authentication module should also enforce
# this as a Pydantic `max_length` on the registration/login request schema.
_BCRYPT_MAX_BYTES = 72


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt. Raises `ValueError` if it exceeds 72 bytes."""
    encoded = plain_password.encode("utf-8")
    if len(encoded) > _BCRYPT_MAX_BYTES:
        raise ValueError(f"Password must not exceed {_BCRYPT_MAX_BYTES} bytes.")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_token(
    subject: str,
    token_type: TokenType = "access",
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Create a signed JWT for `subject` (typically a user ID).

    `token_type` selects the expiry policy (access vs. refresh tokens).
    """
    now = datetime.now(UTC)
    expires_delta = (
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        if token_type == "access"
        else timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )

    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        **(extra_claims or {}),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT, raising `jwt.PyJWTError` subclasses on failure.

    Callers (`app.core.rbac.get_current_user`, `app.services.token_service`)
    are responsible for translating decode errors into `UnauthorizedError`.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def generate_jti() -> str:
    """Generate a unique JWT ID — one per issued token, used to track/revoke it."""
    return uuid.uuid4().hex


def generate_opaque_token() -> str:
    """
    Generate a high-entropy, URL-safe random string for one-time-use tokens
    (password reset links) that don't need JWT's structured claims — just
    unguessability. Never store this raw; see `hash_token`.
    """
    return secrets.token_urlsafe(48)


def hash_token(raw_token: str) -> str:
    """
    SHA-256 hash of a token for at-rest storage (refresh tokens, password
    reset tokens). Unlike passwords, these tokens are already
    high-entropy random values, not human-chosen secrets — a fast
    cryptographic hash is the correct tool here, not bcrypt (which is
    deliberately slow to resist brute-forcing *low*-entropy human input,
    an irrelevant threat model for a 256-bit random token).
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
