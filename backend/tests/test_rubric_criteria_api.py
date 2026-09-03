"""RubricCriterion API tests: CRUD, tenancy, sub-criteria, cross-rubric-parent rejection."""

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.institution import Institution
from app.models.rubric import Rubric
from tests.conftest import auth_headers, create_test_user


async def _login(client: AsyncClient, username: str, password: str = "CorrectHorse9!") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _institution_headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


async def _create_rubric(db_session: AsyncSession, *, code: str) -> Rubric:
    """Builds an Institution + a template Rubric (question_id=None) directly via the ORM."""
    institution = Institution(
        name=f"Institution {code}", code=f"I-{code}", institution_type="university", is_active=True
    )
    db_session.add(institution)
    await db_session.flush()

    rubric = Rubric(
        institution_id=institution.id, name=f"Rubric {code}", total_marks=Decimal("20.00")
    )
    db_session.add(rubric)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(rubric)
    return rubric


def _payload(rubric_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "rubric_id": str(rubric_id),
        "name": "Clarity of expression",
        "max_marks": "5.00",
    }
    payload.update(overrides)
    return payload


async def test_create_rubric_criterion_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rcadmin1", role=seed_rbac["super_admin"])
    rubric = await _create_rubric(db_session, code="CREATE")
    token = await _login(client, "rcadmin1")

    response = await client.post(
        "/api/v1/rubric-criteria",
        json=_payload(rubric.id),
        headers=_institution_headers(token, rubric.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["rubric_id"] == str(rubric.id)
    assert body["name"] == "Clarity of expression"
    assert body["parent_criterion_id"] is None
    assert body["is_mandatory"] is True
    assert body["display_order"] == 0


async def test_create_sub_criterion_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rcadmin2", role=seed_rbac["super_admin"])
    rubric = await _create_rubric(db_session, code="SUBCRIT")
    token = await _login(client, "rcadmin2")
    headers = _institution_headers(token, rubric.institution_id)

    parent_response = await client.post(
        "/api/v1/rubric-criteria", json=_payload(rubric.id, name="Parent"), headers=headers
    )
    assert parent_response.status_code == 201
    parent_id = parent_response.json()["id"]

    child_response = await client.post(
        "/api/v1/rubric-criteria",
        json=_payload(rubric.id, name="Child", parent_criterion_id=parent_id),
        headers=headers,
    )
    assert child_response.status_code == 201
    assert child_response.json()["parent_criterion_id"] == parent_id


async def test_create_rubric_criterion_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rcadmin3", role=seed_rbac["super_admin"])
    rubric = await _create_rubric(db_session, code="NOHEADER")
    token = await _login(client, "rcadmin3")

    response = await client.post(
        "/api/v1/rubric-criteria", json=_payload(rubric.id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_rubric_criterion_rejects_nonexistent_rubric(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rcadmin4", role=seed_rbac["super_admin"])
    rubric = await _create_rubric(db_session, code="BADRUBRIC")
    token = await _login(client, "rcadmin4")

    response = await client.post(
        "/api/v1/rubric-criteria",
        json=_payload(uuid.uuid4()),
        headers=_institution_headers(token, rubric.institution_id),
    )

    assert response.status_code == 404


async def test_create_sub_criterion_rejects_nonexistent_parent(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rcadmin5", role=seed_rbac["super_admin"])
    rubric = await _create_rubric(db_session, code="BADPARENT")
    token = await _login(client, "rcadmin5")

    response = await client.post(
        "/api/v1/rubric-criteria",
        json=_payload(rubric.id, parent_criterion_id=str(uuid.uuid4())),
        headers=_institution_headers(token, rubric.institution_id),
    )

    assert response.status_code == 404


async def test_create_sub_criterion_rejects_cross_rubric_parent(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rcadmin6", role=seed_rbac["super_admin"])
    rubric_a = await _create_rubric(db_session, code="CROSSA")
    token = await _login(client, "rcadmin6")
    headers_a = _institution_headers(token, rubric_a.institution_id)

    parent_response = await client.post(
        "/api/v1/rubric-criteria", json=_payload(rubric_a.id, name="Parent in A"), headers=headers_a
    )
    assert parent_response.status_code == 201
    parent_id = parent_response.json()["id"]

    # A second rubric under the SAME institution (so tenancy alone wouldn't
    # already reject the request) -- the rejection must come from the
    # cross-rubric-parent business rule, not from a 404/tenant mismatch.
    rubric_b = Rubric(
        institution_id=rubric_a.institution_id, name="Rubric B", total_marks=Decimal("10.00")
    )
    db_session.add(rubric_b)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(rubric_b)

    response = await client.post(
        "/api/v1/rubric-criteria",
        json=_payload(rubric_b.id, name="Child in B", parent_criterion_id=parent_id),
        headers=headers_a,
    )

    assert response.status_code == 422


async def test_non_privileged_role_cannot_create_rubric_criterion(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rcstudent1", role=seed_rbac["student"])
    rubric = await _create_rubric(db_session, code="FORBIDDEN")
    token = await _login(client, "rcstudent1")

    response = await client.post(
        "/api/v1/rubric-criteria",
        json=_payload(rubric.id),
        headers=_institution_headers(token, rubric.institution_id),
    )

    assert response.status_code == 403


async def test_get_nonexistent_rubric_criterion_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rcadmin7", role=seed_rbac["super_admin"])
    rubric = await _create_rubric(db_session, code="GETMISSING")
    token = await _login(client, "rcadmin7")

    response = await client.get(
        f"/api/v1/rubric-criteria/{uuid.uuid4()}",
        headers=_institution_headers(token, rubric.institution_id),
    )

    assert response.status_code == 404


async def test_rubric_criterion_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rcadmin8", role=seed_rbac["super_admin"])
    rubric = await _create_rubric(db_session, code="ROUNDTRIP")
    token = await _login(client, "rcadmin8")
    headers = _institution_headers(token, rubric.institution_id)

    created = await client.post(
        "/api/v1/rubric-criteria", json=_payload(rubric.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    original_updated_at = created.json()["updated_at"]

    get_response = await client.get(f"/api/v1/rubric-criteria/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Clarity of expression"

    update_response = await client.patch(
        f"/api/v1/rubric-criteria/{entity_id}",
        json={"display_order": 3, "teacher_notes": "Focus on grammar"},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert updated_body["display_order"] == 3
    assert updated_body["teacher_notes"] == "Focus on grammar"
    # SQLite's func.now() is whole-second resolution -- use >=, not !=.
    assert updated_body["updated_at"] >= original_updated_at

    delete_response = await client.delete(f"/api/v1/rubric-criteria/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/rubric-criteria/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/rubric-criteria/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/rubric-criteria/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/rubric-criteria/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_list_rubric_criteria_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rcadmin9", role=seed_rbac["super_admin"])
    rubric = await _create_rubric(db_session, code="LIST")
    token = await _login(client, "rcadmin9")
    headers = _institution_headers(token, rubric.institution_id)

    for i in range(5):
        response = await client.post(
            "/api/v1/rubric-criteria",
            json=_payload(rubric.id, name=f"Criterion {i}"),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/rubric-criteria?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_rubric_criteria_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rcadmin10", role=seed_rbac["super_admin"])
    rubric = await _create_rubric(db_session, code="BULKOK")
    token = await _login(client, "rcadmin10")
    headers = _institution_headers(token, rubric.institution_id)

    response = await client.post(
        "/api/v1/rubric-criteria/bulk",
        json=[
            _payload(rubric.id, name="Bulk Criterion One"),
            _payload(rubric.id, name="Bulk Criterion Two"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert body["errors"] == []


async def test_bulk_create_rubric_criteria_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rcadmin11", role=seed_rbac["super_admin"])
    rubric = await _create_rubric(db_session, code="BULKERR")
    token = await _login(client, "rcadmin11")
    headers = _institution_headers(token, rubric.institution_id)

    response = await client.post(
        "/api/v1/rubric-criteria/bulk",
        json=[
            _payload(rubric.id, name="Valid Criterion"),
            _payload(uuid.uuid4(), name="Missing Rubric Criterion"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1


async def test_export_rubric_criteria_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rcadmin12", role=seed_rbac["super_admin"])
    rubric = await _create_rubric(db_session, code="EXPORT")
    token = await _login(client, "rcadmin12")
    headers = _institution_headers(token, rubric.institution_id)

    response = await client.get("/api/v1/rubric-criteria/export", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_rubric_criteria_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rcadmin13", role=seed_rbac["super_admin"])
    rubric = await _create_rubric(db_session, code="IMPORT")
    token = await _login(client, "rcadmin13")
    headers = _institution_headers(token, rubric.institution_id)

    response = await client.post("/api/v1/rubric-criteria/import", headers=headers)

    assert response.status_code == 202
    assert response.json()["status"] == "not_implemented"
