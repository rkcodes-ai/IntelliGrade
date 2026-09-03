"""MarkDistribution management API tests: CRUD, tenancy, min/max-score validation."""

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.institution import Institution
from app.models.rubric import Rubric
from app.models.rubric_criterion import RubricCriterion
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


async def _create_criterion(db_session: AsyncSession, *, code: str) -> RubricCriterion:
    """Builds an Institution -> template Rubric -> RubricCriterion chain directly via the ORM."""
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

    criterion = RubricCriterion(
        institution_id=institution.id,
        rubric_id=rubric.id,
        name=f"Criterion {code}",
        max_marks=Decimal("10.00"),
    )
    db_session.add(criterion)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(criterion)
    return criterion


def _payload(rubric_criterion_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "rubric_criterion_id": str(rubric_criterion_id),
        "band_name": "Excellent",
        "min_score": "8.00",
        "max_score": "10.00",
    }
    payload.update(overrides)
    return payload


async def test_create_mark_distribution_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="mdadmin1", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="CREATE")
    token = await _login(client, "mdadmin1")

    response = await client.post(
        "/api/v1/mark-distributions",
        json=_payload(criterion.id),
        headers=_institution_headers(token, criterion.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["rubric_criterion_id"] == str(criterion.id)
    assert body["band_name"] == "Excellent"
    assert body["min_score"] == "8.00"
    assert body["max_score"] == "10.00"


async def test_create_mark_distribution_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="mdadmin2", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="NOHEADER")
    token = await _login(client, "mdadmin2")

    response = await client.post(
        "/api/v1/mark-distributions", json=_payload(criterion.id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_mark_distribution_rejects_nonexistent_criterion(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="mdadmin3", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="BADPARENT")
    token = await _login(client, "mdadmin3")

    response = await client.post(
        "/api/v1/mark-distributions",
        json=_payload(uuid.uuid4()),
        headers=_institution_headers(token, criterion.institution_id),
    )

    assert response.status_code == 404


async def test_create_mark_distribution_rejects_min_above_max(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="mdadmin4", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="BADRANGE")
    token = await _login(client, "mdadmin4")

    response = await client.post(
        "/api/v1/mark-distributions",
        json=_payload(criterion.id, min_score="9.00", max_score="5.00"),
        headers=_institution_headers(token, criterion.institution_id),
    )

    assert response.status_code == 422


async def test_non_privileged_role_cannot_create_mark_distribution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="mdstudent1", role=seed_rbac["student"])
    criterion = await _create_criterion(db_session, code="FORBIDDEN")
    token = await _login(client, "mdstudent1")

    response = await client.post(
        "/api/v1/mark-distributions",
        json=_payload(criterion.id),
        headers=_institution_headers(token, criterion.institution_id),
    )

    assert response.status_code == 403


async def test_get_nonexistent_mark_distribution_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="mdadmin5", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="GETMISSING")
    token = await _login(client, "mdadmin5")

    response = await client.get(
        f"/api/v1/mark-distributions/{uuid.uuid4()}",
        headers=_institution_headers(token, criterion.institution_id),
    )

    assert response.status_code == 404


async def test_mark_distribution_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="mdadmin6", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="ROUNDTRIP")
    token = await _login(client, "mdadmin6")
    headers = _institution_headers(token, criterion.institution_id)

    created = await client.post(
        "/api/v1/mark-distributions", json=_payload(criterion.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    original_updated_at = created.json()["updated_at"]

    get_response = await client.get(f"/api/v1/mark-distributions/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["band_name"] == "Excellent"

    update_response = await client.patch(
        f"/api/v1/mark-distributions/{entity_id}",
        json={"description": "Outstanding work"},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert updated_body["description"] == "Outstanding work"
    # SQLite's func.now() is whole-second resolution -- use >=, not !=.
    assert updated_body["updated_at"] >= original_updated_at

    invalid_update = await client.patch(
        f"/api/v1/mark-distributions/{entity_id}",
        json={"min_score": "9.50", "max_score": "9.00"},
        headers=headers,
    )
    assert invalid_update.status_code == 422

    delete_response = await client.delete(
        f"/api/v1/mark-distributions/{entity_id}", headers=headers
    )
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/mark-distributions/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/mark-distributions/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/mark-distributions/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/mark-distributions/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_list_mark_distributions_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="mdadmin7", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="LIST")
    token = await _login(client, "mdadmin7")
    headers = _institution_headers(token, criterion.institution_id)

    bands = ["Excellent", "Good", "Average", "Poor", "Fail"]
    for i, band in enumerate(bands):
        response = await client.post(
            "/api/v1/mark-distributions",
            json=_payload(
                criterion.id, band_name=band, min_score=f"{i * 2}.00", max_score=f"{i * 2 + 1}.00"
            ),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/mark-distributions?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_mark_distributions_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="mdbulk1", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="BULK")
    token = await _login(client, "mdbulk1")
    headers = _institution_headers(token, criterion.institution_id)

    response = await client.post(
        "/api/v1/mark-distributions/bulk",
        json=[
            _payload(criterion.id, band_name="Excellent", min_score="8.00", max_score="10.00"),
            _payload(criterion.id, band_name="Good", min_score="5.00", max_score="7.99"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert body["errors"] == []


async def test_bulk_create_mark_distributions_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="mdbulk2", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="BULKERR")
    token = await _login(client, "mdbulk2")
    headers = _institution_headers(token, criterion.institution_id)

    response = await client.post(
        "/api/v1/mark-distributions/bulk",
        json=[_payload(criterion.id), _payload(uuid.uuid4())],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["index"] == 1
    assert "message" in body["errors"][0]


async def test_export_mark_distributions_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="mdexport1", role=seed_rbac["super_admin"])
    token = await _login(client, "mdexport1")

    response = await client.get("/api/v1/mark-distributions/export", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_mark_distributions_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="mdimport1", role=seed_rbac["super_admin"])
    token = await _login(client, "mdimport1")

    response = await client.post("/api/v1/mark-distributions/import", headers=auth_headers(token))

    assert response.status_code == 202
    assert response.json()["status"] == "not_implemented"
