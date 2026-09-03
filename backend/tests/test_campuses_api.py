"""Campus management API tests: CRUD, tenancy, soft-delete/restore, bulk-create."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers, create_test_user


async def _login(client: AsyncClient, username: str, password: str = "CorrectHorse9!") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def _create_institution(client: AsyncClient, token: str, code: str = "ACME") -> str:
    response = await client.post(
        "/api/v1/institutions",
        json={"name": f"Institution {code}", "code": code, "institution_type": "university"},
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    result: str = response.json()["id"]
    return result


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Main Campus",
        "code": "MAIN",
        "city": "Springfield",
        "is_main_campus": True,
    }
    payload.update(overrides)
    return payload


async def test_create_campus_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin1", role=seed_rbac["super_admin"])
    token = await _login(client, "admin1")
    institution_id = await _create_institution(client, token, code="INST1")

    response = await client.post(
        "/api/v1/campuses",
        json=_payload(),
        headers={**auth_headers(token), "X-Institution-Id": institution_id},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Main Campus"
    assert body["code"] == "MAIN"
    assert body["institution_id"] == institution_id
    assert body["is_active"] is True


async def test_create_campus_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin2", role=seed_rbac["super_admin"])
    token = await _login(client, "admin2")

    response = await client.post("/api/v1/campuses", json=_payload(), headers=auth_headers(token))

    assert response.status_code == 422


async def test_create_campus_rejects_duplicate_code(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin3", role=seed_rbac["super_admin"])
    token = await _login(client, "admin3")
    institution_id = await _create_institution(client, token, code="INST3")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    first = await client.post("/api/v1/campuses", json=_payload(), headers=headers)
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/campuses", json=_payload(name="Second Campus"), headers=headers
    )
    assert second.status_code == 409


async def test_non_admin_cannot_create_campus(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="student1", role=seed_rbac["student"])
    token = await _login(client, "student1")
    await create_test_user(db_session, username="admin4", role=seed_rbac["super_admin"])
    admin_token = await _login(client, "admin4")
    institution_id = await _create_institution(client, admin_token, code="INST4")

    response = await client.post(
        "/api/v1/campuses",
        json=_payload(),
        headers={**auth_headers(token), "X-Institution-Id": institution_id},
    )

    assert response.status_code == 403


async def test_campus_is_isolated_across_institutions(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin5", role=seed_rbac["super_admin"])
    token = await _login(client, "admin5")
    institution_a = await _create_institution(client, token, code="INSTA")
    institution_b = await _create_institution(client, token, code="INSTB")

    created = await client.post(
        "/api/v1/campuses",
        json=_payload(),
        headers={**auth_headers(token), "X-Institution-Id": institution_a},
    )
    assert created.status_code == 201
    campus_id = created.json()["id"]

    cross_tenant_get = await client.get(
        f"/api/v1/campuses/{campus_id}",
        headers={**auth_headers(token), "X-Institution-Id": institution_b},
    )
    assert cross_tenant_get.status_code == 404


async def test_get_update_and_list_campus(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin6", role=seed_rbac["super_admin"])
    token = await _login(client, "admin6")
    institution_id = await _create_institution(client, token, code="INST6")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    created = await client.post("/api/v1/campuses", json=_payload(), headers=headers)
    campus_id = created.json()["id"]

    get_response = await client.get(f"/api/v1/campuses/{campus_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["code"] == "MAIN"

    update_response = await client.patch(
        f"/api/v1/campuses/{campus_id}", json={"city": "Shelbyville"}, headers=headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["city"] == "Shelbyville"

    list_response = await client.get("/api/v1/campuses", headers=headers)
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] >= 1
    assert any(item["id"] == campus_id for item in body["items"])


async def test_soft_delete_then_restore_campus(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin7", role=seed_rbac["super_admin"])
    token = await _login(client, "admin7")
    institution_id = await _create_institution(client, token, code="INST7")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    created = await client.post("/api/v1/campuses", json=_payload(), headers=headers)
    campus_id = created.json()["id"]

    delete_response = await client.delete(f"/api/v1/campuses/{campus_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/campuses/{campus_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/campuses/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == campus_id for item in deleted_list.json()["items"])

    restore_response = await client.post(f"/api/v1/campuses/{campus_id}/restore", headers=headers)
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/campuses/{campus_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_list_campuses_pagination(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin8", role=seed_rbac["super_admin"])
    token = await _login(client, "admin8")
    institution_id = await _create_institution(client, token, code="INST8")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    for i in range(5):
        response = await client.post(
            "/api/v1/campuses",
            json=_payload(name=f"Campus {i}", code=f"CAMP{i}"),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/campuses?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] >= 5
    assert body["total_pages"] >= 3


async def test_bulk_create_campuses_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin9", role=seed_rbac["super_admin"])
    token = await _login(client, "admin9")
    institution_id = await _create_institution(client, token, code="INST9")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    seed = await client.post("/api/v1/campuses", json=_payload(code="DUP"), headers=headers)
    assert seed.status_code == 201

    response = await client.post(
        "/api/v1/campuses/bulk",
        json=[
            _payload(name="Bulk One", code="BULK1"),
            _payload(name="Bulk Dup", code="DUP"),  # conflicts with the seeded campus
            _payload(name="Bulk Two", code="BULK2"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == "DUP"


async def test_create_campus_rejects_invalid_code_pattern(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin10", role=seed_rbac["super_admin"])
    token = await _login(client, "admin10")
    institution_id = await _create_institution(client, token, code="INST10")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    response = await client.post(
        "/api/v1/campuses", json=_payload(code="lowercase-not-allowed!"), headers=headers
    )

    assert response.status_code == 422
