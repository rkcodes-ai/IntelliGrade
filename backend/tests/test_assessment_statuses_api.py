"""AssessmentStatus management API tests: CRUD, tenancy, soft-delete/restore, pagination."""

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
    payload: dict[str, object] = {"code": "DRAFT", "name": "Draft", "is_terminal": False}
    payload.update(overrides)
    return payload


async def test_create_assessment_status_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="asadmin1", role=seed_rbac["super_admin"])
    token = await _login(client, "asadmin1")
    institution = await _create_institution(db_session)

    response = await client.post(
        "/api/v1/assessment-statuses",
        json=_payload(code="COMPLETED", name="Completed", is_terminal=True),
        headers=_headers(token, institution.id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "COMPLETED"
    assert body["is_terminal"] is True
    assert body["is_active"] is True


async def test_create_assessment_status_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="asadmin2", role=seed_rbac["super_admin"])
    token = await _login(client, "asadmin2")

    response = await client.post(
        "/api/v1/assessment-statuses", json=_payload(), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_assessment_status_rejects_duplicate_code(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="asadmin3", role=seed_rbac["super_admin"])
    token = await _login(client, "asadmin3")
    institution = await _create_institution(db_session)

    first = await client.post(
        "/api/v1/assessment-statuses", json=_payload(), headers=_headers(token, institution.id)
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/assessment-statuses",
        json=_payload(name="Draft 2"),
        headers=_headers(token, institution.id),
    )
    assert second.status_code == 409


async def test_assessment_status_is_tenant_scoped(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="asadmin4", role=seed_rbac["super_admin"])
    token = await _login(client, "asadmin4")
    institution_a = await _create_institution(db_session)
    institution_b = await _create_institution(db_session)

    created = await client.post(
        "/api/v1/assessment-statuses", json=_payload(), headers=_headers(token, institution_a.id)
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    cross_tenant_get = await client.get(
        f"/api/v1/assessment-statuses/{entity_id}", headers=_headers(token, institution_b.id)
    )
    assert cross_tenant_get.status_code == 404


async def test_non_privileged_role_cannot_create_assessment_status(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    student = await create_test_user(db_session, username="asstudent1", role=seed_rbac["student"])
    token = await _login(client, "asstudent1")
    institution = await _create_institution(db_session)
    await _add_membership(db_session, student.id, institution.id)

    response = await client.post(
        "/api/v1/assessment-statuses", json=_payload(), headers=_headers(token, institution.id)
    )

    assert response.status_code == 403


async def test_get_update_soft_delete_and_restore_assessment_status(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="asadmin5", role=seed_rbac["super_admin"])
    token = await _login(client, "asadmin5")
    institution = await _create_institution(db_session)
    headers = _headers(token, institution.id)

    created = await client.post("/api/v1/assessment-statuses", json=_payload(), headers=headers)
    entity_id = created.json()["id"]
    original_updated_at = created.json()["updated_at"]

    get_response = await client.get(f"/api/v1/assessment-statuses/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["code"] == "DRAFT"

    update_response = await client.patch(
        f"/api/v1/assessment-statuses/{entity_id}", json={"is_terminal": True}, headers=headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["is_terminal"] is True
    # SQLite's func.now() is whole-second resolution, so a fast
    # create-then-update can legitimately land in the same second — assert
    # non-decreasing, not strict inequality.
    assert update_response.json()["updated_at"] >= original_updated_at

    delete_response = await client.delete(
        f"/api/v1/assessment-statuses/{entity_id}", headers=headers
    )
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/assessment-statuses/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/assessment-statuses/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/assessment-statuses/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(
        f"/api/v1/assessment-statuses/{entity_id}", headers=headers
    )
    assert get_after_restore.status_code == 200


async def test_get_nonexistent_assessment_status_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="asadmin6", role=seed_rbac["super_admin"])
    token = await _login(client, "asadmin6")
    institution = await _create_institution(db_session)

    response = await client.get(
        f"/api/v1/assessment-statuses/{uuid.uuid4()}", headers=_headers(token, institution.id)
    )

    assert response.status_code == 404


async def test_list_assessment_statuses_pagination(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="asadmin7", role=seed_rbac["super_admin"])
    token = await _login(client, "asadmin7")
    institution = await _create_institution(db_session)
    headers = _headers(token, institution.id)

    for i in range(5):
        response = await client.post(
            "/api/v1/assessment-statuses",
            json=_payload(code=f"STAT{i}", name=f"Status {i}"),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/assessment-statuses?page=1&page_size=2", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_assessment_statuses_collects_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="asadmin8", role=seed_rbac["super_admin"])
    token = await _login(client, "asadmin8")
    institution = await _create_institution(db_session)
    headers = _headers(token, institution.id)

    response = await client.post(
        "/api/v1/assessment-statuses/bulk",
        json=[_payload(code="A"), _payload(code="A"), _payload(code="B")],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


async def test_update_assessment_status_rejects_duplicate_code(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="asadmin9", role=seed_rbac["super_admin"])
    token = await _login(client, "asadmin9")
    institution = await _create_institution(db_session)
    headers = _headers(token, institution.id)

    first = await client.post(
        "/api/v1/assessment-statuses", json=_payload(code="DRAFT"), headers=headers
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/assessment-statuses", json=_payload(code="PUBLISHED"), headers=headers
    )
    assert second.status_code == 201
    second_id = second.json()["id"]

    update_response = await client.patch(
        f"/api/v1/assessment-statuses/{second_id}", json={"code": "DRAFT"}, headers=headers
    )

    assert update_response.status_code == 409
