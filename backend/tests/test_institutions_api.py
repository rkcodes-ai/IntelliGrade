"""Institution management API tests: CRUD, soft-delete/restore, membership."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers, create_test_user


async def _login(client: AsyncClient, username: str, password: str = "CorrectHorse9!") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Acme University",
        "code": "ACME",
        "institution_type": "university",
        "city": "Springfield",
    }
    payload.update(overrides)
    return payload


async def test_create_institution_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin1", role=seed_rbac["super_admin"])
    token = await _login(client, "admin1")

    response = await client.post(
        "/api/v1/institutions", json=_payload(), headers=auth_headers(token)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme University"
    assert body["code"] == "ACME"
    assert body["is_active"] is True


async def test_create_institution_rejects_duplicate_name(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin2", role=seed_rbac["super_admin"])
    token = await _login(client, "admin2")

    first = await client.post(
        "/api/v1/institutions", json=_payload(code="DUPE1"), headers=auth_headers(token)
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/institutions", json=_payload(code="DUPE2"), headers=auth_headers(token)
    )
    assert second.status_code == 409


async def test_create_institution_rejects_duplicate_code(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin3", role=seed_rbac["super_admin"])
    token = await _login(client, "admin3")

    first = await client.post(
        "/api/v1/institutions", json=_payload(name="First University"), headers=auth_headers(token)
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/institutions", json=_payload(name="Second University"), headers=auth_headers(token)
    )
    assert second.status_code == 409


async def test_non_admin_cannot_create_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="student1", role=seed_rbac["student"])
    token = await _login(client, "student1")

    response = await client.post(
        "/api/v1/institutions", json=_payload(), headers=auth_headers(token)
    )

    assert response.status_code == 403


async def test_get_update_and_list_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin4", role=seed_rbac["super_admin"])
    token = await _login(client, "admin4")

    created = await client.post(
        "/api/v1/institutions", json=_payload(), headers=auth_headers(token)
    )
    institution_id = created.json()["id"]

    get_response = await client.get(
        f"/api/v1/institutions/{institution_id}", headers=auth_headers(token)
    )
    assert get_response.status_code == 200
    assert get_response.json()["code"] == "ACME"

    update_response = await client.patch(
        f"/api/v1/institutions/{institution_id}",
        json={"city": "Shelbyville"},
        headers=auth_headers(token),
    )
    assert update_response.status_code == 200
    assert update_response.json()["city"] == "Shelbyville"

    list_response = await client.get("/api/v1/institutions", headers=auth_headers(token))
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] >= 1
    assert any(item["id"] == institution_id for item in body["items"])


async def test_soft_delete_then_restore_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin5", role=seed_rbac["super_admin"])
    token = await _login(client, "admin5")

    created = await client.post(
        "/api/v1/institutions", json=_payload(), headers=auth_headers(token)
    )
    institution_id = created.json()["id"]

    delete_response = await client.delete(
        f"/api/v1/institutions/{institution_id}", headers=auth_headers(token)
    )
    assert delete_response.status_code == 204

    get_after_delete = await client.get(
        f"/api/v1/institutions/{institution_id}", headers=auth_headers(token)
    )
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/institutions/deleted", headers=auth_headers(token))
    assert deleted_list.status_code == 200
    assert any(item["id"] == institution_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/institutions/{institution_id}/restore", headers=auth_headers(token)
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(
        f"/api/v1/institutions/{institution_id}", headers=auth_headers(token)
    )
    assert get_after_restore.status_code == 200


async def test_list_institutions_pagination(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin6", role=seed_rbac["super_admin"])
    token = await _login(client, "admin6")

    for i in range(5):
        response = await client.post(
            "/api/v1/institutions",
            json=_payload(name=f"Institution {i}", code=f"INST{i}"),
            headers=auth_headers(token),
        )
        assert response.status_code == 201

    response = await client.get(
        "/api/v1/institutions?page=1&page_size=2", headers=auth_headers(token)
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] >= 5


async def test_assign_and_revoke_institution_member(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin7", role=seed_rbac["super_admin"])
    member = await create_test_user(db_session, username="member1", role=seed_rbac["teacher"])
    token = await _login(client, "admin7")

    created = await client.post(
        "/api/v1/institutions", json=_payload(), headers=auth_headers(token)
    )
    institution_id = created.json()["id"]

    assign_response = await client.post(
        f"/api/v1/institutions/{institution_id}/members",
        json={"user_id": str(member.id), "is_primary": True},
        headers=auth_headers(token),
    )
    assert assign_response.status_code == 201
    assert assign_response.json()["is_primary"] is True

    duplicate_assign = await client.post(
        f"/api/v1/institutions/{institution_id}/members",
        json={"user_id": str(member.id)},
        headers=auth_headers(token),
    )
    assert duplicate_assign.status_code == 409

    members_response = await client.get(
        f"/api/v1/institutions/{institution_id}/members", headers=auth_headers(token)
    )
    assert members_response.status_code == 200
    assert len(members_response.json()) == 1

    revoke_response = await client.delete(
        f"/api/v1/institutions/{institution_id}/members/{member.id}", headers=auth_headers(token)
    )
    assert revoke_response.status_code == 204

    members_after_revoke = await client.get(
        f"/api/v1/institutions/{institution_id}/members", headers=auth_headers(token)
    )
    assert members_after_revoke.json() == []


async def test_super_admin_sees_all_institutions_in_mine(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin8", role=seed_rbac["super_admin"])
    token = await _login(client, "admin8")

    first = await client.post(
        "/api/v1/institutions",
        json=_payload(name="Mine One", code="MINE1"),
        headers=auth_headers(token),
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/v1/institutions",
        json=_payload(name="Mine Two", code="MINE2"),
        headers=auth_headers(token),
    )
    assert second.status_code == 201

    mine_response = await client.get("/api/v1/institutions/mine", headers=auth_headers(token))
    assert mine_response.status_code == 200
    codes = {item["code"] for item in mine_response.json()}
    assert {"MINE1", "MINE2"}.issubset(codes)


async def test_non_admin_sees_only_their_memberships_in_mine(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin9", role=seed_rbac["super_admin"])
    member = await create_test_user(db_session, username="member2", role=seed_rbac["teacher"])
    admin_token = await _login(client, "admin9")

    institution_a = await client.post(
        "/api/v1/institutions",
        json=_payload(name="Member Inst A", code="MEMBA"),
        headers=auth_headers(admin_token),
    )
    assert institution_a.status_code == 201
    institution_b = await client.post(
        "/api/v1/institutions",
        json=_payload(name="Member Inst B", code="MEMBB"),
        headers=auth_headers(admin_token),
    )
    assert institution_b.status_code == 201

    assign_response = await client.post(
        f"/api/v1/institutions/{institution_a.json()['id']}/members",
        json={"user_id": str(member.id)},
        headers=auth_headers(admin_token),
    )
    assert assign_response.status_code == 201

    member_token = await _login(client, "member2")
    mine_response = await client.get(
        "/api/v1/institutions/mine", headers=auth_headers(member_token)
    )
    assert mine_response.status_code == 200
    codes = {item["code"] for item in mine_response.json()}
    assert codes == {"MEMBA"}
