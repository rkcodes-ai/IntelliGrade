"""AcademicYear management API tests: CRUD, tenancy, and overlap/date-range business rules."""

import uuid
from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.institution import Institution
from tests.conftest import auth_headers, create_test_user


async def _login(client: AsyncClient, username: str, password: str = "CorrectHorse9!") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def _create_institution(db_session: AsyncSession, *, code: str = "INST1") -> Institution:
    institution = Institution(
        name=f"Institution {code}", code=code, institution_type="university", is_active=True
    )
    db_session.add(institution)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(institution)
    return institution


def _institution_headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


async def test_create_academic_year_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ayadmin1", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="INST-CREATE")
    token = await _login(client, "ayadmin1")

    response = await client.post(
        "/api/v1/academic-years",
        json={
            "year_label": "2025-2026",
            "start_date": "2025-06-01",
            "end_date": "2026-05-31",
        },
        headers=_institution_headers(token, institution.id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["year_label"] == "2025-2026"
    assert body["status"] == "planned"
    assert body["is_current"] is False
    assert body["institution_id"] == str(institution.id)


async def test_create_academic_year_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ayadmin2", role=seed_rbac["super_admin"])
    token = await _login(client, "ayadmin2")

    response = await client.post(
        "/api/v1/academic-years",
        json={
            "year_label": "2025-2026",
            "start_date": "2025-06-01",
            "end_date": "2026-05-31",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_academic_year_rejects_invalid_date_range(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ayadmin3", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="INST-BADRANGE")
    token = await _login(client, "ayadmin3")

    response = await client.post(
        "/api/v1/academic-years",
        json={
            "year_label": "2025-2026",
            "start_date": "2026-05-31",
            "end_date": "2025-06-01",
        },
        headers=_institution_headers(token, institution.id),
    )

    assert response.status_code == 422


async def test_create_academic_year_rejects_duplicate_label(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ayadmin4", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="INST-DUPE")
    token = await _login(client, "ayadmin4")

    first = await client.post(
        "/api/v1/academic-years",
        json={
            "year_label": "2025-2026",
            "start_date": "2025-06-01",
            "end_date": "2026-05-31",
        },
        headers=_institution_headers(token, institution.id),
    )
    assert first.status_code == 201

    duplicate = await client.post(
        "/api/v1/academic-years",
        json={
            "year_label": "2025-2026",
            "start_date": "2027-06-01",
            "end_date": "2028-05-31",
        },
        headers=_institution_headers(token, institution.id),
    )
    assert duplicate.status_code == 409


async def test_create_academic_year_rejects_overlapping_dates(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ayadmin5", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="INST-OVERLAP")
    token = await _login(client, "ayadmin5")

    first = await client.post(
        "/api/v1/academic-years",
        json={
            "year_label": "2025-2026",
            "start_date": "2025-06-01",
            "end_date": "2026-05-31",
        },
        headers=_institution_headers(token, institution.id),
    )
    assert first.status_code == 201

    overlapping = await client.post(
        "/api/v1/academic-years",
        json={
            "year_label": "2026-2027",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
        headers=_institution_headers(token, institution.id),
    )
    assert overlapping.status_code == 409
    assert "overlap" in overlapping.json()["error"]["message"].lower()


async def test_non_privileged_role_cannot_create_academic_year(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aystudent1", role=seed_rbac["student"])
    institution = await _create_institution(db_session, code="INST-STUDENT")
    token = await _login(client, "aystudent1")

    response = await client.post(
        "/api/v1/academic-years",
        json={
            "year_label": "2025-2026",
            "start_date": "2025-06-01",
            "end_date": "2026-05-31",
        },
        headers=_institution_headers(token, institution.id),
    )

    assert response.status_code == 403


async def test_academic_year_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ayadmin6", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="INST-ROUNDTRIP")
    token = await _login(client, "ayadmin6")
    headers = _institution_headers(token, institution.id)

    create_response = await client.post(
        "/api/v1/academic-years",
        json={
            "year_label": "2025-2026",
            "start_date": "2025-06-01",
            "end_date": "2026-05-31",
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]

    get_response = await client.get(f"/api/v1/academic-years/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["year_label"] == "2025-2026"

    update_response = await client.patch(
        f"/api/v1/academic-years/{entity_id}",
        json={"status": "active", "is_current": True},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "active"
    assert update_response.json()["is_current"] is True

    delete_response = await client.delete(f"/api/v1/academic-years/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/academic-years/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/academic-years/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/academic-years/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200
    assert restore_response.json()["id"] == entity_id

    get_after_restore = await client.get(f"/api/v1/academic-years/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_academic_year_get_nonexistent_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ayadmin7", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="INST-404")
    token = await _login(client, "ayadmin7")

    response = await client.get(
        f"/api/v1/academic-years/{uuid.uuid4()}",
        headers=_institution_headers(token, institution.id),
    )
    assert response.status_code == 404


async def test_list_academic_years_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ayadmin8", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="INST-LIST")
    token = await _login(client, "ayadmin8")
    headers = _institution_headers(token, institution.id)

    base_start = date(2020, 6, 1)
    for i in range(5):
        start = base_start.replace(year=base_start.year + i * 2)
        end = start.replace(year=start.year + 1)
        create_response = await client.post(
            "/api/v1/academic-years",
            json={
                "year_label": f"{start.year}-{end.year}",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            },
            headers=headers,
        )
        assert create_response.status_code == 201

    response = await client.get("/api/v1/academic-years?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2


async def test_bulk_create_academic_years_collects_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ayadmin9", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="INST-BULK")
    token = await _login(client, "ayadmin9")
    headers = _institution_headers(token, institution.id)

    response = await client.post(
        "/api/v1/academic-years/bulk",
        json=[
            {"year_label": "2025-2026", "start_date": "2025-06-01", "end_date": "2026-05-31"},
            {"year_label": "2025-2026", "start_date": "2025-06-01", "end_date": "2026-05-31"},
            {"year_label": "2027-2028", "start_date": "2027-06-01", "end_date": "2028-05-31"},
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


async def test_academic_year_import_export_skeleton_endpoints(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ayadmin10", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="INST-IMPEXP")
    token = await _login(client, "ayadmin10")
    headers = _institution_headers(token, institution.id)

    import_response = await client.post("/api/v1/academic-years/import", headers=headers)
    assert import_response.status_code == 202
    assert import_response.json()["status"] == "not_implemented"

    export_response = await client.get("/api/v1/academic-years/export", headers=headers)
    assert export_response.status_code == 200
    assert export_response.json()["status"] == "not_implemented"
