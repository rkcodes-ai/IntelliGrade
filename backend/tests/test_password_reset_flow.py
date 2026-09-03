"""
End-to-end forgot/reset-password flow tests.

The reset token is never returned in the API response (see
`AuthService.request_password_reset`) — these tests read it directly from
the database (mirroring how a real email-delivery integration would
extract it before sending) rather than from the HTTP response.
"""

from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_opaque_token, hash_token
from app.models.password_reset_token import PasswordResetToken
from tests.conftest import create_test_user


async def _issue_reset_token(client: AsyncClient, db_session: AsyncSession, email: str) -> str:
    """
    Request a password reset and capture the raw token — normally only its
    hash is ever persisted (see `PasswordResetToken`), so the only way to
    get the raw value for testing is to intercept it at generation time,
    the way a real email-delivery integration would.

    Patches `app.services.auth_service.generate_opaque_token` specifically
    (not `app.core.security.generate_opaque_token`, where it's defined) —
    `auth_service.py` imports it via `from ... import generate_opaque_token`,
    which binds the name into its own module namespace at import time, so
    patching the origin module doesn't affect the already-bound reference.
    """
    from app.services.auth_service import AuthService, RequestContext

    service = AuthService(db_session)
    real_token = generate_opaque_token()
    with patch("app.services.auth_service.generate_opaque_token", return_value=real_token):
        await service.request_password_reset(email, RequestContext())
    return real_token


async def test_reset_password_with_valid_token_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(
        db_session, email="reset@example.com", username="resetuser", password="OldPassword9!"
    )

    raw_token = await _issue_reset_token(client, db_session, "reset@example.com")

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "NewPassword9!"},
    )
    assert response.status_code == 200

    login_response = await client.post(
        "/api/v1/auth/login", json={"identifier": "resetuser", "password": "NewPassword9!"}
    )
    assert login_response.status_code == 200


async def test_reset_token_cannot_be_reused(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(
        db_session, email="reset2@example.com", username="resetuser2", password="OldPassword9!"
    )
    raw_token = await _issue_reset_token(client, db_session, "reset2@example.com")

    first = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "NewPassword9!"},
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "AnotherPassword9!"},
    )
    assert second.status_code == 401


async def test_reset_password_with_invalid_token_fails(client: AsyncClient, seed_rbac) -> None:
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": "NewPassword9!"},
    )
    assert response.status_code == 401


async def test_expired_reset_token_is_rejected(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    from datetime import UTC, datetime, timedelta

    user = await create_test_user(
        db_session, email="expired@example.com", username="expireduser", password="OldPassword9!"
    )
    raw_token = "a-fixed-test-token-value"
    db_session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "NewPassword9!"},
    )
    assert response.status_code == 401


async def test_reset_password_revokes_existing_sessions(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(
        db_session, email="revoke@example.com", username="revokeuser", password="OldPassword9!"
    )
    login_response = await client.post(
        "/api/v1/auth/login", json={"identifier": "revokeuser", "password": "OldPassword9!"}
    )
    assert login_response.status_code == 200

    raw_token = await _issue_reset_token(client, db_session, "revoke@example.com")
    await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "NewPassword9!"},
    )

    # The refresh cookie from the pre-reset login must no longer work.
    refresh_response = await client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 401


async def test_new_password_cannot_match_the_old_one_within_history(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(
        db_session, email="reuse@example.com", username="reuseuser", password="OriginalPass9!"
    )
    login_response = await client.post(
        "/api/v1/auth/login", json={"identifier": "reuseuser", "password": "OriginalPass9!"}
    )
    token = login_response.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "OriginalPass9!", "new_password": "OriginalPass9!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "different from your last" in response.json()["error"]["message"]
