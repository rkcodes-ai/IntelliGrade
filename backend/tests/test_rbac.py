"""
RBAC enforcement tests: role/permission checks at the API boundary, plus
role assignment/revocation. These exercise `require_permissions` and
`require_roles` through real requests, not by calling the dependency
functions directly — the whole point is verifying the wiring, not just the
logic in isolation (that's covered by `test_rbac_service.py`).
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers, create_test_user


async def _login(client: AsyncClient, username: str, password: str = "CorrectHorse9!") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def test_student_cannot_list_users(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="student1", role=seed_rbac["student"])
    token = await _login(client, "student1")

    response = await client.get("/api/v1/users", headers=auth_headers(token))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_super_admin_can_list_users(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin1", role=seed_rbac["super_admin"])
    token = await _login(client, "admin1")

    response = await client.get("/api/v1/users", headers=auth_headers(token))

    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_user_with_no_roles_has_no_permissions(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="noroles")
    token = await _login(client, "noroles")

    response = await client.get("/api/v1/roles", headers=auth_headers(token))

    assert response.status_code == 403


async def test_list_roles_returns_seeded_roles(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin2", role=seed_rbac["super_admin"])
    token = await _login(client, "admin2")

    response = await client.get("/api/v1/roles", headers=auth_headers(token))

    assert response.status_code == 200
    names = {role["name"] for role in response.json()}
    assert names == {"super_admin", "institution_admin", "teacher", "student"}


async def test_super_admin_role_includes_every_permission(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin3", role=seed_rbac["super_admin"])
    token = await _login(client, "admin3")

    response = await client.get("/api/v1/permissions", headers=auth_headers(token))
    all_codes = {p["code"] for p in response.json()}

    roles_response = await client.get("/api/v1/roles", headers=auth_headers(token))
    super_admin_role = next(r for r in roles_response.json() if r["name"] == "super_admin")

    assert set(super_admin_role["permissions"]) == all_codes


async def test_assign_role_grants_new_permissions(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin4", role=seed_rbac["super_admin"])
    admin_token = await _login(client, "admin4")

    await create_test_user(db_session, username="plainuser")

    # Before: no role, no access.
    plain_token = await _login(client, "plainuser")
    forbidden = await client.get("/api/v1/roles", headers=auth_headers(plain_token))
    assert forbidden.status_code == 403

    # Admin grants the "teacher" role.
    users_response = await client.get("/api/v1/users", headers=auth_headers(admin_token))
    plain_user_id = next(u["id"] for u in users_response.json() if u["username"] == "plainuser")

    assign_response = await client.post(
        f"/api/v1/users/{plain_user_id}/roles",
        json={"role_name": "teacher"},
        headers=auth_headers(admin_token),
    )
    assert assign_response.status_code == 200
    assert "teacher" in assign_response.json()["roles"]

    # After: a fresh login picks up the new role's permissions.
    new_plain_token = await _login(client, "plainuser")
    now_allowed = await client.get("/api/v1/sessions", headers=auth_headers(new_plain_token))
    assert now_allowed.status_code == 200


async def test_assigning_the_same_role_twice_is_a_conflict(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin5", role=seed_rbac["super_admin"])
    target = await create_test_user(db_session, username="target1", role=seed_rbac["teacher"])
    admin_token = await _login(client, "admin5")

    response = await client.post(
        f"/api/v1/users/{target.id}/roles",
        json={"role_name": "teacher"},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_revoke_role_removes_access(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin6", role=seed_rbac["super_admin"])
    target = await create_test_user(db_session, username="target2", role=seed_rbac["teacher"])
    admin_token = await _login(client, "admin6")

    revoke_response = await client.delete(
        f"/api/v1/users/{target.id}/roles/teacher", headers=auth_headers(admin_token)
    )
    assert revoke_response.status_code == 200
    assert "teacher" not in revoke_response.json()["roles"]


async def test_missing_bearer_token_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/v1/roles")
    assert response.status_code == 401


async def test_malformed_bearer_token_is_rejected(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/roles", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


async def test_deactivated_user_token_is_rejected_on_next_request(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin7", role=seed_rbac["super_admin"])
    target = await create_test_user(db_session, username="target3", password="CorrectHorse9!")
    admin_token = await _login(client, "admin7")
    target_token = await _login(client, "target3")

    deactivate_response = await client.post(
        f"/api/v1/users/{target.id}/deactivate", headers=auth_headers(admin_token)
    )
    assert deactivate_response.status_code == 200

    # The target's still-valid (not expired) access token must stop working
    # the moment the account is deactivated — get_current_user re-checks
    # `is_active` from the database on every request, not just at login.
    response = await client.get("/api/v1/users/me", headers=auth_headers(target_token))
    assert response.status_code == 401
