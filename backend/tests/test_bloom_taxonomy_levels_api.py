"""BloomTaxonomyLevel management API tests: CRUD, tenancy, soft-delete/restore, pagination."""

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
        "code": "REMEMBER",
        "name": "Remember",
        "level_order": 1,
        "description": "Recall facts and basic concepts",
    }
    payload.update(overrides)
    return payload


async def test_create_bloom_taxonomy_level_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin1", role=seed_rbac["super_admin"])
    token = await _login(client, "admin1")
    institution = await _create_institution(db_session)

    response = await client.post(
        "/api/v1/bloom-taxonomy-levels", json=_payload(), headers=_headers(token, institution.id)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "REMEMBER"
    assert body["name"] == "Remember"
    assert body["level_order"] == 1
    assert body["is_active"] is True
    assert body["institution_id"] == str(institution.id)


async def test_create_bloom_taxonomy_level_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin2", role=seed_rbac["super_admin"])
    token = await _login(client, "admin2")

    response = await client.post(
        "/api/v1/bloom-taxonomy-levels", json=_payload(), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_bloom_taxonomy_level_rejects_duplicate_code(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin3", role=seed_rbac["super_admin"])
    token = await _login(client, "admin3")
    institution = await _create_institution(db_session)

    first = await client.post(
        "/api/v1/bloom-taxonomy-levels", json=_payload(), headers=_headers(token, institution.id)
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/bloom-taxonomy-levels",
        json=_payload(name="Remember 2"),
        headers=_headers(token, institution.id),
    )
    assert second.status_code == 409


async def test_bloom_taxonomy_level_is_tenant_scoped(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin4", role=seed_rbac["super_admin"])
    token = await _login(client, "admin4")
    institution_a = await _create_institution(db_session)
    institution_b = await _create_institution(db_session)

    created = await client.post(
        "/api/v1/bloom-taxonomy-levels", json=_payload(), headers=_headers(token, institution_a.id)
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    other = await client.post(
        "/api/v1/bloom-taxonomy-levels", json=_payload(), headers=_headers(token, institution_b.id)
    )
    assert other.status_code == 201

    cross_tenant_get = await client.get(
        f"/api/v1/bloom-taxonomy-levels/{entity_id}", headers=_headers(token, institution_b.id)
    )
    assert cross_tenant_get.status_code == 404


async def test_non_privileged_role_cannot_create_bloom_taxonomy_level(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    student = await create_test_user(db_session, username="student1", role=seed_rbac["student"])
    token = await _login(client, "student1")
    institution = await _create_institution(db_session)
    await _add_membership(db_session, student.id, institution.id)

    response = await client.post(
        "/api/v1/bloom-taxonomy-levels", json=_payload(), headers=_headers(token, institution.id)
    )

    assert response.status_code == 403


async def test_get_update_soft_delete_and_restore_bloom_taxonomy_level(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin5", role=seed_rbac["super_admin"])
    token = await _login(client, "admin5")
    institution = await _create_institution(db_session)
    headers = _headers(token, institution.id)

    created = await client.post("/api/v1/bloom-taxonomy-levels", json=_payload(), headers=headers)
    entity_id = created.json()["id"]
    created_updated_at = created.json()["updated_at"]

    get_response = await client.get(f"/api/v1/bloom-taxonomy-levels/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["code"] == "REMEMBER"

    update_response = await client.patch(
        f"/api/v1/bloom-taxonomy-levels/{entity_id}",
        json={"name": "Updated Remember", "level_order": 2},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Remember"
    assert update_response.json()["level_order"] == 2
    # SQLite's func.now() is whole-second resolution, so use >= rather than
    # != to avoid flakiness when create+update land in the same second.
    assert update_response.json()["updated_at"] >= created_updated_at

    delete_response = await client.delete(
        f"/api/v1/bloom-taxonomy-levels/{entity_id}", headers=headers
    )
    assert delete_response.status_code == 204

    get_after_delete = await client.get(
        f"/api/v1/bloom-taxonomy-levels/{entity_id}", headers=headers
    )
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/bloom-taxonomy-levels/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/bloom-taxonomy-levels/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200
    assert restore_response.json()["updated_at"] >= created_updated_at

    get_after_restore = await client.get(
        f"/api/v1/bloom-taxonomy-levels/{entity_id}", headers=headers
    )
    assert get_after_restore.status_code == 200


async def test_get_nonexistent_bloom_taxonomy_level_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin6", role=seed_rbac["super_admin"])
    token = await _login(client, "admin6")
    institution = await _create_institution(db_session)
    headers = _headers(token, institution.id)

    response = await client.get(f"/api/v1/bloom-taxonomy-levels/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404


async def test_list_bloom_taxonomy_levels_pagination(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin7", role=seed_rbac["super_admin"])
    token = await _login(client, "admin7")
    institution = await _create_institution(db_session)
    headers = _headers(token, institution.id)

    for i in range(5):
        response = await client.post(
            "/api/v1/bloom-taxonomy-levels",
            json=_payload(code=f"LVL{i}", name=f"Level {i}", level_order=i),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/bloom-taxonomy-levels?page=1&page_size=2", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_bloom_taxonomy_levels_collects_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin8", role=seed_rbac["super_admin"])
    token = await _login(client, "admin8")
    institution = await _create_institution(db_session)
    headers = _headers(token, institution.id)

    response = await client.post(
        "/api/v1/bloom-taxonomy-levels/bulk",
        json=[_payload(code="A"), _payload(code="A"), _payload(code="B")],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


async def test_update_bloom_taxonomy_level_rejects_duplicate_code(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin10", role=seed_rbac["super_admin"])
    token = await _login(client, "admin10")
    institution = await _create_institution(db_session)
    headers = _headers(token, institution.id)

    first = await client.post(
        "/api/v1/bloom-taxonomy-levels", json=_payload(code="UNDERSTAND"), headers=headers
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/bloom-taxonomy-levels", json=_payload(code="APPLY"), headers=headers
    )
    assert second.status_code == 201
    second_id = second.json()["id"]

    update_response = await client.patch(
        f"/api/v1/bloom-taxonomy-levels/{second_id}",
        json={"code": "UNDERSTAND"},
        headers=headers,
    )

    assert update_response.status_code == 409


async def test_bloom_taxonomy_level_import_export_skeleton_endpoints(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="admin9", role=seed_rbac["super_admin"])
    token = await _login(client, "admin9")
    institution = await _create_institution(db_session)
    headers = _headers(token, institution.id)

    import_response = await client.post("/api/v1/bloom-taxonomy-levels/import", headers=headers)
    assert import_response.status_code == 202
    assert import_response.json()["status"] == "not_implemented"

    export_response = await client.get("/api/v1/bloom-taxonomy-levels/export", headers=headers)
    assert export_response.status_code == 200
    assert export_response.json()["status"] == "not_implemented"
