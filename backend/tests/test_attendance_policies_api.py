"""AttendancePolicy management API tests: CRUD, tenancy, business rules, pagination."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.institution import Institution
from app.models.user_institution import UserInstitution
from tests.conftest import auth_headers, create_test_user


async def _login(client: AsyncClient, username: str, password: str = "CorrectHorse9!") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def _create_institution(db_session: AsyncSession) -> Institution:
    suffix = uuid.uuid4().hex[:8]
    institution = Institution(
        name=f"Test Institution {suffix}",
        code=f"INST{suffix.upper()}",
        institution_type="university",
    )
    db_session.add(institution)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(institution)
    return institution


async def _add_membership(
    db_session: AsyncSession, user_id: uuid.UUID, institution_id: uuid.UUID
) -> None:
    db_session.add(UserInstitution(user_id=user_id, institution_id=institution_id, is_active=True))
    await db_session.commit()


def _headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    return {**auth_headers(token), "X-Institution-Id": str(institution_id)}


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Standard Attendance",
        "minimum_attendance_percentage": 75,
        "condonation_percentage": 10,
    }
    payload.update(overrides)
    return payload


async def test_create_attendance_policy_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin1", role=seed_rbac["super_admin"])
    token = await _login(client, "admin1")
    institution = await _create_institution(db_session)

    response = await client.post(
        "/api/v1/attendance-policies", json=_payload(), headers=_headers(token, institution.id)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Standard Attendance"
    assert float(body["minimum_attendance_percentage"]) == 75
    assert body["is_active"] is True


async def test_create_attendance_policy_accepts_unvalidated_program_id(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """`program_id` is a plain FK that is deliberately NOT validated against the
    `programs` table (Program is owned by a different, parallel agent)."""
    await create_test_user(db_session, username="admin1b", role=seed_rbac["super_admin"])
    token = await _login(client, "admin1b")
    institution = await _create_institution(db_session)
    fake_program_id = str(uuid.uuid4())

    response = await client.post(
        "/api/v1/attendance-policies",
        json=_payload(program_id=fake_program_id),
        headers=_headers(token, institution.id),
    )

    assert response.status_code == 201
    assert response.json()["program_id"] == fake_program_id


async def test_create_attendance_policy_rejects_condonation_above_minimum(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin1c", role=seed_rbac["super_admin"])
    token = await _login(client, "admin1c")
    institution = await _create_institution(db_session)

    response = await client.post(
        "/api/v1/attendance-policies",
        json=_payload(minimum_attendance_percentage=75, condonation_percentage=80),
        headers=_headers(token, institution.id),
    )

    assert response.status_code == 422


async def test_update_attendance_policy_rejects_condonation_above_minimum(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin1d", role=seed_rbac["super_admin"])
    token = await _login(client, "admin1d")
    institution = await _create_institution(db_session)
    headers = _headers(token, institution.id)

    created = await client.post(
        "/api/v1/attendance-policies",
        json=_payload(minimum_attendance_percentage=75, condonation_percentage=10),
        headers=headers,
    )
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/attendance-policies/{entity_id}",
        json={"minimum_attendance_percentage": 5},
        headers=headers,
    )

    assert update_response.status_code == 422


async def test_create_attendance_policy_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin2", role=seed_rbac["super_admin"])
    token = await _login(client, "admin2")

    response = await client.post(
        "/api/v1/attendance-policies", json=_payload(), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_attendance_policy_rejects_duplicate_name(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin3", role=seed_rbac["super_admin"])
    token = await _login(client, "admin3")
    institution = await _create_institution(db_session)

    first = await client.post(
        "/api/v1/attendance-policies", json=_payload(), headers=_headers(token, institution.id)
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/attendance-policies",
        json=_payload(minimum_attendance_percentage=80),
        headers=_headers(token, institution.id),
    )
    assert second.status_code == 409


async def test_attendance_policy_is_tenant_scoped(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin4", role=seed_rbac["super_admin"])
    token = await _login(client, "admin4")
    institution_a = await _create_institution(db_session)
    institution_b = await _create_institution(db_session)

    created = await client.post(
        "/api/v1/attendance-policies", json=_payload(), headers=_headers(token, institution_a.id)
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    cross_tenant_get = await client.get(
        f"/api/v1/attendance-policies/{entity_id}", headers=_headers(token, institution_b.id)
    )
    assert cross_tenant_get.status_code == 404


async def test_non_privileged_role_cannot_create_attendance_policy(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    student = await create_test_user(db_session, username="student1", role=seed_rbac["student"])
    token = await _login(client, "student1")
    institution = await _create_institution(db_session)
    await _add_membership(db_session, student.id, institution.id)

    response = await client.post(
        "/api/v1/attendance-policies", json=_payload(), headers=_headers(token, institution.id)
    )

    assert response.status_code == 403


async def test_get_update_soft_delete_and_restore_attendance_policy(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin5", role=seed_rbac["super_admin"])
    token = await _login(client, "admin5")
    institution = await _create_institution(db_session)
    headers = _headers(token, institution.id)

    created = await client.post("/api/v1/attendance-policies", json=_payload(), headers=headers)
    entity_id = created.json()["id"]

    get_response = await client.get(f"/api/v1/attendance-policies/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Standard Attendance"

    update_response = await client.patch(
        f"/api/v1/attendance-policies/{entity_id}",
        json={"minimum_attendance_percentage": 85},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert float(update_response.json()["minimum_attendance_percentage"]) == 85

    delete_response = await client.delete(
        f"/api/v1/attendance-policies/{entity_id}", headers=headers
    )
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/attendance-policies/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/attendance-policies/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/attendance-policies/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(
        f"/api/v1/attendance-policies/{entity_id}", headers=headers
    )
    assert get_after_restore.status_code == 200


async def test_list_attendance_policies_pagination(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin6", role=seed_rbac["super_admin"])
    token = await _login(client, "admin6")
    institution = await _create_institution(db_session)
    headers = _headers(token, institution.id)

    for i in range(5):
        response = await client.post(
            "/api/v1/attendance-policies", json=_payload(name=f"Policy {i}"), headers=headers
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/attendance-policies?page=1&page_size=2", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_attendance_policies_collects_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin7", role=seed_rbac["super_admin"])
    token = await _login(client, "admin7")
    institution = await _create_institution(db_session)
    headers = _headers(token, institution.id)

    response = await client.post(
        "/api/v1/attendance-policies/bulk",
        json=[_payload(name="Bulk A"), _payload(name="Bulk A"), _payload(name="Bulk B")],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1
