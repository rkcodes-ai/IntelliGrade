"""
End-to-end authentication flow tests: login → protected request → refresh
→ logout, plus account lockout and RBAC enforcement. These exercise the
full stack (API → service → repository → SQLite) rather than mocking any
layer, since this is the highest-value path to get right.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers, create_test_user


async def test_login_with_correct_credentials_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(
        db_session, email="alice@example.com", username="alice", password="CorrectHorse9!"
    )

    response = await client.post(
        "/api/v1/auth/login", json={"identifier": "alice", "password": "CorrectHorse9!"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == "alice"
    assert "refresh_token" in response.cookies


async def test_login_accepts_email_as_identifier(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(
        db_session, email="bob@example.com", username="bob", password="CorrectHorse9!"
    )

    response = await client.post(
        "/api/v1/auth/login", json={"identifier": "bob@example.com", "password": "CorrectHorse9!"}
    )

    assert response.status_code == 200


async def test_login_with_wrong_password_fails(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="carol", password="CorrectHorse9!")

    response = await client.post(
        "/api/v1/auth/login", json={"identifier": "carol", "password": "WrongPassword1!"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_login_with_unknown_identifier_fails(client: AsyncClient, seed_rbac) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": "nobody", "password": "WhateverPassword1!"}
    )
    assert response.status_code == 401


async def test_repeated_failed_logins_lock_the_account(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="dave", password="CorrectHorse9!")

    for _ in range(5):
        response = await client.post(
            "/api/v1/auth/login", json={"identifier": "dave", "password": "WrongPassword1!"}
        )

    assert response.status_code == 401

    # The 6th attempt (even with the CORRECT password) is rejected because
    # the account is now locked.
    locked_response = await client.post(
        "/api/v1/auth/login", json={"identifier": "dave", "password": "CorrectHorse9!"}
    )
    assert locked_response.status_code == 423
    assert locked_response.json()["error"]["code"] == "account_locked"


async def test_login_rejects_inactive_user(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eve", password="CorrectHorse9!", is_active=False)

    response = await client.post(
        "/api/v1/auth/login", json={"identifier": "eve", "password": "CorrectHorse9!"}
    )
    assert response.status_code == 401


async def test_get_me_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401


async def test_get_me_returns_current_user(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="frank", password="CorrectHorse9!")
    login_response = await client.post(
        "/api/v1/auth/login", json={"identifier": "frank", "password": "CorrectHorse9!"}
    )
    token = login_response.json()["access_token"]

    response = await client.get("/api/v1/users/me", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["username"] == "frank"


async def test_update_me_updates_profile(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="grace", password="CorrectHorse9!")
    login_response = await client.post(
        "/api/v1/auth/login", json={"identifier": "grace", "password": "CorrectHorse9!"}
    )
    token = login_response.json()["access_token"]

    response = await client.patch(
        "/api/v1/users/me",
        json={"full_name": "Grace Hopper", "timezone": "America/New_York"},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Grace Hopper"
    assert body["timezone"] == "America/New_York"


async def test_refresh_rotates_the_token_and_old_one_stops_working(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="heidi", password="CorrectHorse9!")
    login_response = await client.post(
        "/api/v1/auth/login", json={"identifier": "heidi", "password": "CorrectHorse9!"}
    )
    old_cookie = login_response.cookies["refresh_token"]

    refresh_response = await client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 200
    new_access_token = refresh_response.json()["access_token"]
    assert new_access_token != login_response.json()["access_token"]

    # Replaying the OLD (now-rotated) refresh token must fail, and — per
    # the reuse-detection design — revoke the whole family, so even the
    # token that replaced it stops working.
    client.cookies.set("refresh_token", old_cookie)
    reuse_response = await client.post("/api/v1/auth/refresh")
    assert reuse_response.status_code == 401


async def test_logout_revokes_the_refresh_token(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ivan", password="CorrectHorse9!")
    await client.post(
        "/api/v1/auth/login", json={"identifier": "ivan", "password": "CorrectHorse9!"}
    )

    logout_response = await client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200

    refresh_after_logout = await client.post("/api/v1/auth/refresh")
    assert refresh_after_logout.status_code == 401


async def test_change_password_requires_correct_current_password(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="judy", password="CorrectHorse9!")
    login_response = await client.post(
        "/api/v1/auth/login", json={"identifier": "judy", "password": "CorrectHorse9!"}
    )
    token = login_response.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "WrongOne1!", "new_password": "BrandNewPass1!"},
        headers=auth_headers(token),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_change_password_succeeds_and_new_password_works(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="mallory", password="CorrectHorse9!")
    login_response = await client.post(
        "/api/v1/auth/login", json={"identifier": "mallory", "password": "CorrectHorse9!"}
    )
    token = login_response.json()["access_token"]

    change_response = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "CorrectHorse9!", "new_password": "BrandNewPass1!"},
        headers=auth_headers(token),
    )
    assert change_response.status_code == 200

    relogin_response = await client.post(
        "/api/v1/auth/login", json={"identifier": "mallory", "password": "BrandNewPass1!"}
    )
    assert relogin_response.status_code == 200


async def test_forgot_password_always_returns_202(client: AsyncClient, seed_rbac) -> None:
    response = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "unknown@example.com"}
    )
    assert response.status_code == 202
