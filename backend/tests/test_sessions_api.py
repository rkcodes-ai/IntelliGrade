"""Session management API tests: list, revoke, and the "current session" flag."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers, create_test_user


async def test_list_sessions_shows_current_session_after_login(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="alice", role=seed_rbac["student"])
    login_response = await client.post(
        "/api/v1/auth/login", json={"identifier": "alice", "password": "CorrectHorse9!"}
    )
    token = login_response.json()["access_token"]

    response = await client.get("/api/v1/sessions", headers=auth_headers(token))

    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) == 1
    assert sessions[0]["is_current"] is True
    assert sessions[0]["is_active"] is True


async def test_multiple_logins_create_multiple_sessions(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bob", role=seed_rbac["student"])

    first_login = await client.post(
        "/api/v1/auth/login", json={"identifier": "bob", "password": "CorrectHorse9!"}
    )
    token = first_login.json()["access_token"]

    # A second "device" logging in (same credentials, cookies cleared to
    # simulate a different browser) creates a second session row without
    # disturbing the first. Session listing uses the bearer token, not
    # cookies, so the first token still works to inspect the result.
    client.cookies.clear()
    await client.post(
        "/api/v1/auth/login", json={"identifier": "bob", "password": "CorrectHorse9!"}
    )

    response = await client.get("/api/v1/sessions", headers=auth_headers(token))
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_revoke_session_deactivates_it(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="carol", role=seed_rbac["student"])
    login_response = await client.post(
        "/api/v1/auth/login", json={"identifier": "carol", "password": "CorrectHorse9!"}
    )
    token = login_response.json()["access_token"]

    sessions = (await client.get("/api/v1/sessions", headers=auth_headers(token))).json()
    session_id = sessions[0]["id"]

    revoke_response = await client.delete(
        f"/api/v1/sessions/{session_id}", headers=auth_headers(token)
    )
    assert revoke_response.status_code == 204

    # Revoking the session also revokes its backing refresh token family —
    # a subsequent refresh attempt using that cookie must fail.
    refresh_response = await client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 401


async def test_cannot_revoke_another_users_session(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="dave", role=seed_rbac["student"])
    await create_test_user(db_session, username="erin", role=seed_rbac["student"])

    dave_login = await client.post(
        "/api/v1/auth/login", json={"identifier": "dave", "password": "CorrectHorse9!"}
    )
    dave_token = dave_login.json()["access_token"]
    dave_sessions = (await client.get("/api/v1/sessions", headers=auth_headers(dave_token))).json()
    dave_session_id = dave_sessions[0]["id"]

    client.cookies.clear()
    erin_login = await client.post(
        "/api/v1/auth/login", json={"identifier": "erin", "password": "CorrectHorse9!"}
    )
    erin_token = erin_login.json()["access_token"]

    response = await client.delete(
        f"/api/v1/sessions/{dave_session_id}", headers=auth_headers(erin_token)
    )
    assert response.status_code == 403


async def test_sessions_require_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/sessions")
    assert response.status_code == 401
