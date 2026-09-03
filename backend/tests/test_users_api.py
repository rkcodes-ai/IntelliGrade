"""User management API tests: admin CRUD, activate/deactivate, soft delete."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers, create_test_user


async def _login(client: AsyncClient, username: str, password: str = "CorrectHorse9!") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def test_create_user_as_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin1", role=seed_rbac["super_admin"])
    token = await _login(client, "admin1")

    response = await client.post(
        "/api/v1/users",
        json={
            "email": "newperson@example.com",
            "username": "newperson",
            "password": "StrongPass9!",
            "full_name": "New Person",
            "role_names": ["student"],
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "newperson"
    assert body["roles"] == ["student"]
    assert "password" not in body
    assert "hashed_password" not in body


async def test_create_user_rejects_weak_password(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin2", role=seed_rbac["super_admin"])
    token = await _login(client, "admin2")

    response = await client.post(
        "/api/v1/users",
        json={
            "email": "weak@example.com",
            "username": "weakpass",
            "password": "weak",
            "full_name": "Weak Pass",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_user_rejects_duplicate_email(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin3", role=seed_rbac["super_admin"])
    await create_test_user(db_session, username="existing", email="dupe@example.com")
    token = await _login(client, "admin3")

    response = await client.post(
        "/api/v1/users",
        json={
            "email": "dupe@example.com",
            "username": "someoneelse",
            "password": "StrongPass9!",
            "full_name": "Someone Else",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 409


async def test_non_admin_cannot_create_user(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="plain1", role=seed_rbac["student"])
    token = await _login(client, "plain1")

    response = await client.post(
        "/api/v1/users",
        json={
            "email": "x@example.com",
            "username": "x",
            "password": "StrongPass9!",
            "full_name": "X",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 403


async def test_get_user_by_id(client: AsyncClient, db_session: AsyncSession, seed_rbac) -> None:
    await create_test_user(db_session, username="admin4", role=seed_rbac["super_admin"])
    target = await create_test_user(db_session, username="target1")
    token = await _login(client, "admin4")

    response = await client.get(f"/api/v1/users/{target.id}", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["username"] == "target1"


async def test_update_user_as_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin5", role=seed_rbac["super_admin"])
    target = await create_test_user(db_session, username="target2")
    token = await _login(client, "admin5")

    response = await client.patch(
        f"/api/v1/users/{target.id}",
        json={"full_name": "Updated Name"},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"


async def test_deactivate_then_activate_user(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin6", role=seed_rbac["super_admin"])
    target = await create_test_user(db_session, username="target3")
    token = await _login(client, "admin6")

    deactivate = await client.post(
        f"/api/v1/users/{target.id}/deactivate", headers=auth_headers(token)
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False

    activate = await client.post(f"/api/v1/users/{target.id}/activate", headers=auth_headers(token))
    assert activate.status_code == 200
    assert activate.json()["is_active"] is True


async def test_soft_delete_removes_user_from_list_and_login(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin7", role=seed_rbac["super_admin"])
    target = await create_test_user(db_session, username="target4", password="CorrectHorse9!")
    token = await _login(client, "admin7")

    delete_response = await client.delete(f"/api/v1/users/{target.id}", headers=auth_headers(token))
    assert delete_response.status_code == 204

    get_response = await client.get(f"/api/v1/users/{target.id}", headers=auth_headers(token))
    assert get_response.status_code == 404

    login_response = await client.post(
        "/api/v1/auth/login", json={"identifier": "target4", "password": "CorrectHorse9!"}
    )
    assert login_response.status_code == 401


async def test_list_users_pagination_params(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin8", role=seed_rbac["super_admin"])
    for i in range(5):
        await create_test_user(db_session, username=f"bulk{i}")
    token = await _login(client, "admin8")

    response = await client.get("/api/v1/users?limit=2&offset=0", headers=auth_headers(token))

    assert response.status_code == 200
    assert len(response.json()) == 2
