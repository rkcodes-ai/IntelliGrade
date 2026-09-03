"""Department management API tests: CRUD, campus-scoped uniqueness, tenancy."""

import uuid

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


async def _create_campus(
    client: AsyncClient, token: str, institution_id: str, code: str = "MAIN"
) -> str:
    response = await client.post(
        "/api/v1/campuses",
        json={"name": f"Campus {code}", "code": code},
        headers={**auth_headers(token), "X-Institution-Id": institution_id},
    )
    assert response.status_code == 201
    result: str = response.json()["id"]
    return result


def _payload(campus_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "campus_id": campus_id,
        "name": "Computer Science",
        "code": "CSE",
        "description": "Department of Computer Science",
    }
    payload.update(overrides)
    return payload


async def test_create_department_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin1", role=seed_rbac["super_admin"])
    token = await _login(client, "admin1")
    institution_id = await _create_institution(client, token, code="INST1")
    campus_id = await _create_campus(client, token, institution_id)
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    response = await client.post("/api/v1/departments", json=_payload(campus_id), headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Computer Science"
    assert body["code"] == "CSE"
    assert body["campus_id"] == campus_id
    assert body["institution_id"] == institution_id


async def test_create_department_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin2", role=seed_rbac["super_admin"])
    token = await _login(client, "admin2")
    institution_id = await _create_institution(client, token, code="INST2")
    campus_id = await _create_campus(client, token, institution_id)

    response = await client.post(
        "/api/v1/departments", json=_payload(campus_id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_department_rejects_duplicate_code_within_campus(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin3", role=seed_rbac["super_admin"])
    token = await _login(client, "admin3")
    institution_id = await _create_institution(client, token, code="INST3")
    campus_id = await _create_campus(client, token, institution_id)
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    first = await client.post("/api/v1/departments", json=_payload(campus_id), headers=headers)
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/departments", json=_payload(campus_id, name="CS Again"), headers=headers
    )
    assert second.status_code == 409


async def test_create_department_allows_same_code_in_different_campus(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """Uniqueness is scoped per-campus, not per-institution."""
    await create_test_user(db_session, username="admin4", role=seed_rbac["super_admin"])
    token = await _login(client, "admin4")
    institution_id = await _create_institution(client, token, code="INST4")
    campus_a = await _create_campus(client, token, institution_id, code="CAMPA")
    campus_b = await _create_campus(client, token, institution_id, code="CAMPB")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    first = await client.post("/api/v1/departments", json=_payload(campus_a), headers=headers)
    assert first.status_code == 201

    second = await client.post("/api/v1/departments", json=_payload(campus_b), headers=headers)
    assert second.status_code == 201


async def test_create_department_fails_404_for_nonexistent_campus(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin5", role=seed_rbac["super_admin"])
    token = await _login(client, "admin5")
    institution_id = await _create_institution(client, token, code="INST5")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    response = await client.post(
        "/api/v1/departments", json=_payload(str(uuid.uuid4())), headers=headers
    )

    assert response.status_code == 404


async def test_create_department_fails_404_for_campus_in_different_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin6", role=seed_rbac["super_admin"])
    token = await _login(client, "admin6")
    institution_a = await _create_institution(client, token, code="INSTA")
    institution_b = await _create_institution(client, token, code="INSTB")
    campus_in_a = await _create_campus(client, token, institution_a)

    response = await client.post(
        "/api/v1/departments",
        json=_payload(campus_in_a),
        headers={**auth_headers(token), "X-Institution-Id": institution_b},
    )

    assert response.status_code == 404


async def test_non_admin_cannot_create_department(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="student1", role=seed_rbac["student"])
    token = await _login(client, "student1")
    await create_test_user(db_session, username="admin7", role=seed_rbac["super_admin"])
    admin_token = await _login(client, "admin7")
    institution_id = await _create_institution(client, admin_token, code="INST7")
    campus_id = await _create_campus(client, admin_token, institution_id)

    response = await client.post(
        "/api/v1/departments",
        json=_payload(campus_id),
        headers={**auth_headers(token), "X-Institution-Id": institution_id},
    )

    assert response.status_code == 403


async def test_get_update_and_list_department(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin8", role=seed_rbac["super_admin"])
    token = await _login(client, "admin8")
    institution_id = await _create_institution(client, token, code="INST8")
    campus_id = await _create_campus(client, token, institution_id)
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    created = await client.post("/api/v1/departments", json=_payload(campus_id), headers=headers)
    department_id = created.json()["id"]

    get_response = await client.get(f"/api/v1/departments/{department_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["code"] == "CSE"

    update_response = await client.patch(
        f"/api/v1/departments/{department_id}",
        json={"description": "Renamed description"},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["description"] == "Renamed description"

    list_response = await client.get("/api/v1/departments", headers=headers)
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] >= 1
    assert any(item["id"] == department_id for item in body["items"])


async def test_update_department_rejects_move_to_campus_in_different_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin9", role=seed_rbac["super_admin"])
    token = await _login(client, "admin9")
    institution_a = await _create_institution(client, token, code="INSTA2")
    institution_b = await _create_institution(client, token, code="INSTB2")
    campus_a = await _create_campus(client, token, institution_a)
    campus_b = await _create_campus(client, token, institution_b)

    created = await client.post(
        "/api/v1/departments",
        json=_payload(campus_a),
        headers={**auth_headers(token), "X-Institution-Id": institution_a},
    )
    assert created.status_code == 201
    department_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/departments/{department_id}",
        json={"campus_id": campus_b},
        headers={**auth_headers(token), "X-Institution-Id": institution_a},
    )

    assert update_response.status_code == 404


async def test_soft_delete_then_restore_department(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin10", role=seed_rbac["super_admin"])
    token = await _login(client, "admin10")
    institution_id = await _create_institution(client, token, code="INST10")
    campus_id = await _create_campus(client, token, institution_id)
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    created = await client.post("/api/v1/departments", json=_payload(campus_id), headers=headers)
    department_id = created.json()["id"]

    delete_response = await client.delete(f"/api/v1/departments/{department_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/departments/{department_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/departments/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == department_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/departments/{department_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/departments/{department_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_list_departments_pagination(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin11", role=seed_rbac["super_admin"])
    token = await _login(client, "admin11")
    institution_id = await _create_institution(client, token, code="INST11")
    campus_id = await _create_campus(client, token, institution_id)
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    for i in range(5):
        response = await client.post(
            "/api/v1/departments",
            json=_payload(campus_id, name=f"Dept {i}", code=f"DEPT{i}"),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/departments?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] >= 5


async def test_bulk_create_departments_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin12", role=seed_rbac["super_admin"])
    token = await _login(client, "admin12")
    institution_id = await _create_institution(client, token, code="INST12")
    campus_id = await _create_campus(client, token, institution_id)
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    response = await client.post(
        "/api/v1/departments/bulk",
        json=[
            _payload(campus_id, name="Bulk One", code="BULK1"),
            _payload(str(uuid.uuid4()), name="Bad Campus", code="BULK2"),
            _payload(campus_id, name="Bulk Three", code="BULK3"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


async def test_department_import_export_skeleton_endpoints(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin13", role=seed_rbac["super_admin"])
    token = await _login(client, "admin13")
    institution_id = await _create_institution(client, token, code="INST13")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    import_response = await client.post("/api/v1/departments/import", headers=headers)
    assert import_response.status_code == 202
    assert import_response.json()["status"] == "not_implemented"

    export_response = await client.get("/api/v1/departments/export", headers=headers)
    assert export_response.status_code == 200
    assert export_response.json()["status"] == "not_implemented"
