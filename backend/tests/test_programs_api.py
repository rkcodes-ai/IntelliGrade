"""Program management API tests: CRUD, department-scoped uniqueness, validation."""

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


async def _create_department(
    client: AsyncClient, token: str, institution_id: str, campus_id: str, code: str = "CSE"
) -> str:
    response = await client.post(
        "/api/v1/departments",
        json={"campus_id": campus_id, "name": f"Department {code}", "code": code},
        headers={**auth_headers(token), "X-Institution-Id": institution_id},
    )
    assert response.status_code == 201
    result: str = response.json()["id"]
    return result


def _payload(department_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "department_id": department_id,
        "name": "B.Tech Computer Science",
        "code": "BTCSE",
        "degree_type": "ug",
        "duration_years": 4,
        "total_semesters": 8,
    }
    payload.update(overrides)
    return payload


async def _setup_department(
    client: AsyncClient, token: str, institution_code: str = "INST1"
) -> tuple[str, str]:
    institution_id = await _create_institution(client, token, code=institution_code)
    campus_id = await _create_campus(client, token, institution_id)
    department_id = await _create_department(client, token, institution_id, campus_id)
    return institution_id, department_id


async def test_create_program_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin1", role=seed_rbac["super_admin"])
    token = await _login(client, "admin1")
    institution_id, department_id = await _setup_department(client, token, "INST1")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    response = await client.post("/api/v1/programs", json=_payload(department_id), headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "B.Tech Computer Science"
    assert body["code"] == "BTCSE"
    assert body["degree_type"] == "ug"
    assert body["duration_years"] == 4
    assert body["total_semesters"] == 8
    assert body["department_id"] == department_id
    assert body["institution_id"] == institution_id


async def test_create_program_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin2", role=seed_rbac["super_admin"])
    token = await _login(client, "admin2")
    _, department_id = await _setup_department(client, token, "INST2")

    response = await client.post(
        "/api/v1/programs", json=_payload(department_id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_program_rejects_duplicate_code_within_department(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin3", role=seed_rbac["super_admin"])
    token = await _login(client, "admin3")
    institution_id, department_id = await _setup_department(client, token, "INST3")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    first = await client.post("/api/v1/programs", json=_payload(department_id), headers=headers)
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/programs", json=_payload(department_id, name="Again"), headers=headers
    )
    assert second.status_code == 409


async def test_create_program_fails_404_for_nonexistent_department(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin4", role=seed_rbac["super_admin"])
    token = await _login(client, "admin4")
    institution_id = await _create_institution(client, token, code="INST4")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    response = await client.post(
        "/api/v1/programs", json=_payload(str(uuid.uuid4())), headers=headers
    )

    assert response.status_code == 404


async def test_create_program_fails_404_for_department_in_different_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin5", role=seed_rbac["super_admin"])
    token = await _login(client, "admin5")
    _, department_in_a = await _setup_department(client, token, "INSTA")
    institution_b = await _create_institution(client, token, code="INSTB")

    response = await client.post(
        "/api/v1/programs",
        json=_payload(department_in_a),
        headers={**auth_headers(token), "X-Institution-Id": institution_b},
    )

    assert response.status_code == 404


async def test_create_program_rejects_zero_duration_years(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin6", role=seed_rbac["super_admin"])
    token = await _login(client, "admin6")
    institution_id, department_id = await _setup_department(client, token, "INST6")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    response = await client.post(
        "/api/v1/programs",
        json=_payload(department_id, duration_years=0),
        headers=headers,
    )

    assert response.status_code == 422


async def test_create_program_rejects_zero_total_semesters(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin7", role=seed_rbac["super_admin"])
    token = await _login(client, "admin7")
    institution_id, department_id = await _setup_department(client, token, "INST7")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    response = await client.post(
        "/api/v1/programs",
        json=_payload(department_id, total_semesters=0),
        headers=headers,
    )

    assert response.status_code == 422


async def test_create_program_rejects_invalid_degree_type(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin8", role=seed_rbac["super_admin"])
    token = await _login(client, "admin8")
    institution_id, department_id = await _setup_department(client, token, "INST8")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    response = await client.post(
        "/api/v1/programs",
        json=_payload(department_id, degree_type="not_a_real_degree"),
        headers=headers,
    )

    assert response.status_code == 422


async def test_non_admin_cannot_create_program(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="student1", role=seed_rbac["student"])
    token = await _login(client, "student1")
    await create_test_user(db_session, username="admin9", role=seed_rbac["super_admin"])
    admin_token = await _login(client, "admin9")
    institution_id, department_id = await _setup_department(client, admin_token, "INST9")

    response = await client.post(
        "/api/v1/programs",
        json=_payload(department_id),
        headers={**auth_headers(token), "X-Institution-Id": institution_id},
    )

    assert response.status_code == 403


async def test_get_update_and_list_program(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin10", role=seed_rbac["super_admin"])
    token = await _login(client, "admin10")
    institution_id, department_id = await _setup_department(client, token, "INST10")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    created = await client.post("/api/v1/programs", json=_payload(department_id), headers=headers)
    program_id = created.json()["id"]

    get_response = await client.get(f"/api/v1/programs/{program_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["code"] == "BTCSE"

    update_response = await client.patch(
        f"/api/v1/programs/{program_id}", json={"duration_years": 5}, headers=headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["duration_years"] == 5

    list_response = await client.get("/api/v1/programs", headers=headers)
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] >= 1
    assert any(item["id"] == program_id for item in body["items"])


async def test_update_program_rejects_invalid_duration_years(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin11", role=seed_rbac["super_admin"])
    token = await _login(client, "admin11")
    institution_id, department_id = await _setup_department(client, token, "INST11")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    created = await client.post("/api/v1/programs", json=_payload(department_id), headers=headers)
    program_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/programs/{program_id}", json={"total_semesters": 0}, headers=headers
    )
    assert update_response.status_code == 422


async def test_soft_delete_then_restore_program(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin12", role=seed_rbac["super_admin"])
    token = await _login(client, "admin12")
    institution_id, department_id = await _setup_department(client, token, "INST12")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    created = await client.post("/api/v1/programs", json=_payload(department_id), headers=headers)
    program_id = created.json()["id"]

    delete_response = await client.delete(f"/api/v1/programs/{program_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/programs/{program_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/programs/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == program_id for item in deleted_list.json()["items"])

    restore_response = await client.post(f"/api/v1/programs/{program_id}/restore", headers=headers)
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/programs/{program_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_list_programs_pagination(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin13", role=seed_rbac["super_admin"])
    token = await _login(client, "admin13")
    institution_id, department_id = await _setup_department(client, token, "INST13")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    for i in range(5):
        response = await client.post(
            "/api/v1/programs",
            json=_payload(department_id, name=f"Program {i}", code=f"PROG{i}"),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/programs?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] >= 5


async def test_bulk_create_programs_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin14", role=seed_rbac["super_admin"])
    token = await _login(client, "admin14")
    institution_id, department_id = await _setup_department(client, token, "INST14")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    response = await client.post(
        "/api/v1/programs/bulk",
        json=[
            _payload(department_id, name="Bulk One", code="BULK1"),
            _payload(str(uuid.uuid4()), name="Bad Department", code="BULK2"),
            _payload(department_id, name="Bulk Three", code="BULK3"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


async def test_program_import_export_skeleton_endpoints(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin15", role=seed_rbac["super_admin"])
    token = await _login(client, "admin15")
    institution_id, _department_id = await _setup_department(client, token, "INST15")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    import_response = await client.post("/api/v1/programs/import", headers=headers)
    assert import_response.status_code == 202
    assert import_response.json()["status"] == "not_implemented"

    export_response = await client.get("/api/v1/programs/export", headers=headers)
    assert export_response.status_code == 200
    assert export_response.json()["status"] == "not_implemented"
