"""Room management API tests: CRUD, tenancy, and parent-FK/uniqueness business rules."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campus import Campus
from app.models.institution import Institution
from tests.conftest import auth_headers, create_test_user


async def _login(client: AsyncClient, username: str, password: str = "CorrectHorse9!") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def _create_campus(db_session: AsyncSession, *, code: str = "CAMP1") -> Campus:
    institution = Institution(
        name=f"Institution {code}", code=f"I-{code}", institution_type="university", is_active=True
    )
    db_session.add(institution)
    await db_session.flush()

    campus = Campus(institution_id=institution.id, name=f"Campus {code}", code=f"C-{code}")
    db_session.add(campus)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(campus)
    return campus


def _institution_headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


async def test_create_room_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="roomadmin1", role=seed_rbac["super_admin"])
    campus = await _create_campus(db_session, code="CREATE")
    token = await _login(client, "roomadmin1")

    response = await client.post(
        "/api/v1/rooms",
        json={
            "campus_id": str(campus.id),
            "name": "101",
            "building": "Main Block",
            "floor": "1",
            "capacity": 60,
            "room_type": "classroom",
        },
        headers=_institution_headers(token, campus.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "101"
    assert body["room_type"] == "classroom"
    assert body["capacity"] == 60
    assert body["is_active"] is True


async def test_create_room_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="roomadmin2", role=seed_rbac["super_admin"])
    campus = await _create_campus(db_session, code="NOHEADER")
    token = await _login(client, "roomadmin2")

    response = await client.post(
        "/api/v1/rooms",
        json={"campus_id": str(campus.id), "name": "101", "capacity": 30, "room_type": "classroom"},
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_room_rejects_duplicate_name_within_campus(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="roomadmin3", role=seed_rbac["super_admin"])
    campus = await _create_campus(db_session, code="DUPE")
    token = await _login(client, "roomadmin3")
    headers = _institution_headers(token, campus.institution_id)

    first = await client.post(
        "/api/v1/rooms",
        json={"campus_id": str(campus.id), "name": "101", "capacity": 30, "room_type": "classroom"},
        headers=headers,
    )
    assert first.status_code == 201

    duplicate = await client.post(
        "/api/v1/rooms",
        json={"campus_id": str(campus.id), "name": "101", "capacity": 40, "room_type": "lab"},
        headers=headers,
    )
    assert duplicate.status_code == 409


async def test_create_room_rejects_nonexistent_campus(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="roomadmin4", role=seed_rbac["super_admin"])
    campus = await _create_campus(db_session, code="BADPARENT")
    token = await _login(client, "roomadmin4")

    response = await client.post(
        "/api/v1/rooms",
        json={
            "campus_id": str(uuid.uuid4()),
            "name": "101",
            "capacity": 30,
            "room_type": "classroom",
        },
        headers=_institution_headers(token, campus.institution_id),
    )

    assert response.status_code == 404


async def test_create_room_rejects_invalid_room_type(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="roomadmin5", role=seed_rbac["super_admin"])
    campus = await _create_campus(db_session, code="BADTYPE")
    token = await _login(client, "roomadmin5")

    response = await client.post(
        "/api/v1/rooms",
        json={
            "campus_id": str(campus.id),
            "name": "101",
            "capacity": 30,
            "room_type": "not_a_real_type",
        },
        headers=_institution_headers(token, campus.institution_id),
    )

    assert response.status_code == 422


async def test_non_privileged_role_cannot_create_room(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="roomstudent1", role=seed_rbac["student"])
    campus = await _create_campus(db_session, code="FORBIDDEN")
    token = await _login(client, "roomstudent1")

    response = await client.post(
        "/api/v1/rooms",
        json={"campus_id": str(campus.id), "name": "101", "capacity": 30, "room_type": "classroom"},
        headers=_institution_headers(token, campus.institution_id),
    )

    assert response.status_code == 403


async def test_room_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="roomadmin6", role=seed_rbac["super_admin"])
    campus = await _create_campus(db_session, code="ROUNDTRIP")
    token = await _login(client, "roomadmin6")
    headers = _institution_headers(token, campus.institution_id)

    create_response = await client.post(
        "/api/v1/rooms",
        json={"campus_id": str(campus.id), "name": "101", "capacity": 30, "room_type": "classroom"},
        headers=headers,
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]

    get_response = await client.get(f"/api/v1/rooms/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "101"

    update_response = await client.patch(
        f"/api/v1/rooms/{entity_id}", json={"capacity": 45}, headers=headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["capacity"] == 45

    delete_response = await client.delete(f"/api/v1/rooms/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/rooms/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/rooms/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(f"/api/v1/rooms/{entity_id}/restore", headers=headers)
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/rooms/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_list_rooms_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="roomadmin7", role=seed_rbac["super_admin"])
    campus = await _create_campus(db_session, code="LIST")
    token = await _login(client, "roomadmin7")
    headers = _institution_headers(token, campus.institution_id)

    for i in range(5):
        create_response = await client.post(
            "/api/v1/rooms",
            json={
                "campus_id": str(campus.id),
                "name": f"10{i}",
                "capacity": 30,
                "room_type": "classroom",
            },
            headers=headers,
        )
        assert create_response.status_code == 201

    response = await client.get("/api/v1/rooms?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_rooms_collects_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="roomadmin8", role=seed_rbac["super_admin"])
    campus = await _create_campus(db_session, code="BULK")
    token = await _login(client, "roomadmin8")
    headers = _institution_headers(token, campus.institution_id)

    response = await client.post(
        "/api/v1/rooms/bulk",
        json=[
            {"campus_id": str(campus.id), "name": "B1", "capacity": 30, "room_type": "classroom"},
            {"campus_id": str(campus.id), "name": "B1", "capacity": 30, "room_type": "classroom"},
            {"campus_id": str(campus.id), "name": "B2", "capacity": 30, "room_type": "classroom"},
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


async def test_room_import_export_skeleton_endpoints(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="roomadmin9", role=seed_rbac["super_admin"])
    campus = await _create_campus(db_session, code="IMPEXP")
    token = await _login(client, "roomadmin9")
    headers = _institution_headers(token, campus.institution_id)

    import_response = await client.post("/api/v1/rooms/import", headers=headers)
    assert import_response.status_code == 202
    assert import_response.json()["status"] == "not_implemented"

    export_response = await client.get("/api/v1/rooms/export", headers=headers)
    assert export_response.status_code == 200
    assert export_response.json()["status"] == "not_implemented"
