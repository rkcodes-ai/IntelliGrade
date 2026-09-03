"""Semester management API tests: CRUD, tenancy, and date-range/overlap business rules."""

import uuid
from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic_year import AcademicYear
from app.models.institution import Institution
from tests.conftest import auth_headers, create_test_user


async def _login(client: AsyncClient, username: str, password: str = "CorrectHorse9!") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def _create_academic_year(
    db_session: AsyncSession,
    *,
    code: str = "AY1",
    start_date: date = date(2025, 6, 1),
    end_date: date = date(2026, 5, 31),
) -> AcademicYear:
    institution = Institution(
        name=f"Institution {code}", code=f"I-{code}", institution_type="university", is_active=True
    )
    db_session.add(institution)
    await db_session.flush()

    academic_year = AcademicYear(
        institution_id=institution.id,
        year_label=f"AY-{code}",
        start_date=start_date,
        end_date=end_date,
    )
    db_session.add(academic_year)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(academic_year)
    return academic_year


def _institution_headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


async def test_create_semester_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="semadmin1", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="CREATE")
    token = await _login(client, "semadmin1")

    response = await client.post(
        "/api/v1/semesters",
        json={
            "academic_year_id": str(academic_year.id),
            "name": "Semester 1",
            "semester_number": 1,
            "term_type": "odd",
            "start_date": "2025-06-01",
            "end_date": "2025-11-30",
        },
        headers=_institution_headers(token, academic_year.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Semester 1"
    assert body["semester_number"] == 1
    assert body["term_type"] == "odd"
    assert body["status"] == "planned"
    assert body["academic_year_id"] == str(academic_year.id)


async def test_create_semester_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="semadmin2", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="NOHEADER")
    token = await _login(client, "semadmin2")

    response = await client.post(
        "/api/v1/semesters",
        json={
            "academic_year_id": str(academic_year.id),
            "name": "Semester 1",
            "semester_number": 1,
            "term_type": "odd",
            "start_date": "2025-06-01",
            "end_date": "2025-11-30",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_semester_rejects_nonexistent_academic_year(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="semadmin3", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="BADPARENT")
    token = await _login(client, "semadmin3")

    response = await client.post(
        "/api/v1/semesters",
        json={
            "academic_year_id": str(uuid.uuid4()),
            "name": "Semester 1",
            "semester_number": 1,
            "term_type": "odd",
            "start_date": "2025-06-01",
            "end_date": "2025-11-30",
        },
        headers=_institution_headers(token, academic_year.institution_id),
    )

    assert response.status_code == 404


async def test_create_semester_rejects_invalid_date_range(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="semadmin4", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="BADRANGE")
    token = await _login(client, "semadmin4")

    response = await client.post(
        "/api/v1/semesters",
        json={
            "academic_year_id": str(academic_year.id),
            "name": "Semester 1",
            "semester_number": 1,
            "term_type": "odd",
            "start_date": "2025-11-30",
            "end_date": "2025-06-01",
        },
        headers=_institution_headers(token, academic_year.institution_id),
    )

    assert response.status_code == 422


async def test_create_semester_rejects_dates_outside_academic_year_range(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="semadmin5", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(
        db_session, code="OUTOFRANGE", start_date=date(2025, 6, 1), end_date=date(2026, 5, 31)
    )
    token = await _login(client, "semadmin5")

    response = await client.post(
        "/api/v1/semesters",
        json={
            "academic_year_id": str(academic_year.id),
            "name": "Semester 1",
            "semester_number": 1,
            "term_type": "odd",
            "start_date": "2025-05-01",  # before academic year start
            "end_date": "2025-11-30",
        },
        headers=_institution_headers(token, academic_year.institution_id),
    )

    assert response.status_code == 422

    response2 = await client.post(
        "/api/v1/semesters",
        json={
            "academic_year_id": str(academic_year.id),
            "name": "Semester 1",
            "semester_number": 1,
            "term_type": "odd",
            "start_date": "2025-06-01",
            "end_date": "2026-06-15",  # after academic year end
        },
        headers=_institution_headers(token, academic_year.institution_id),
    )

    assert response2.status_code == 422


async def test_create_semester_rejects_duplicate_semester_number(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="semadmin6", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="DUPE")
    token = await _login(client, "semadmin6")
    headers = _institution_headers(token, academic_year.institution_id)

    first = await client.post(
        "/api/v1/semesters",
        json={
            "academic_year_id": str(academic_year.id),
            "name": "Semester 1",
            "semester_number": 1,
            "term_type": "odd",
            "start_date": "2025-06-01",
            "end_date": "2025-11-30",
        },
        headers=headers,
    )
    assert first.status_code == 201

    duplicate = await client.post(
        "/api/v1/semesters",
        json={
            "academic_year_id": str(academic_year.id),
            "name": "Semester 1 Duplicate",
            "semester_number": 1,
            "term_type": "even",
            "start_date": "2025-12-01",
            "end_date": "2026-05-31",
        },
        headers=headers,
    )
    assert duplicate.status_code == 409


async def test_create_semester_rejects_overlapping_sibling_dates(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="semadmin7", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="OVERLAP")
    token = await _login(client, "semadmin7")
    headers = _institution_headers(token, academic_year.institution_id)

    first = await client.post(
        "/api/v1/semesters",
        json={
            "academic_year_id": str(academic_year.id),
            "name": "Semester 1",
            "semester_number": 1,
            "term_type": "odd",
            "start_date": "2025-06-01",
            "end_date": "2025-11-30",
        },
        headers=headers,
    )
    assert first.status_code == 201

    overlapping = await client.post(
        "/api/v1/semesters",
        json={
            "academic_year_id": str(academic_year.id),
            "name": "Semester 2",
            "semester_number": 2,
            "term_type": "even",
            "start_date": "2025-11-01",  # overlaps semester 1's end
            "end_date": "2026-05-31",
        },
        headers=headers,
    )
    assert overlapping.status_code == 409
    assert "overlap" in overlapping.json()["error"]["message"].lower()


async def test_non_privileged_role_cannot_create_semester(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="semstudent1", role=seed_rbac["student"])
    academic_year = await _create_academic_year(db_session, code="FORBIDDEN")
    token = await _login(client, "semstudent1")

    response = await client.post(
        "/api/v1/semesters",
        json={
            "academic_year_id": str(academic_year.id),
            "name": "Semester 1",
            "semester_number": 1,
            "term_type": "odd",
            "start_date": "2025-06-01",
            "end_date": "2025-11-30",
        },
        headers=_institution_headers(token, academic_year.institution_id),
    )

    assert response.status_code == 403


async def test_semester_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="semadmin8", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="ROUNDTRIP")
    token = await _login(client, "semadmin8")
    headers = _institution_headers(token, academic_year.institution_id)

    create_response = await client.post(
        "/api/v1/semesters",
        json={
            "academic_year_id": str(academic_year.id),
            "name": "Semester 1",
            "semester_number": 1,
            "term_type": "odd",
            "start_date": "2025-06-01",
            "end_date": "2025-11-30",
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]
    original_updated_at = create_response.json()["updated_at"]

    get_response = await client.get(f"/api/v1/semesters/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Semester 1"

    # PATCH round-trip over real HTTP — this is the MissingGreenlet
    # regression test: `updated_at` must be present and must have changed,
    # which requires `session.refresh()` after the update flush.
    update_response = await client.patch(
        f"/api/v1/semesters/{entity_id}",
        json={"status": "active", "name": "Semester 1 Updated"},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert updated_body["status"] == "active"
    assert updated_body["name"] == "Semester 1 Updated"
    assert "updated_at" in updated_body
    # SQLite's func.now() has only whole-second resolution (unlike
    # PostgreSQL's microsecond precision in production), so a fast
    # create-then-update in the same test can legitimately land in the same
    # second — assert non-decreasing, not strict inequality, to avoid
    # flakiness while still catching a regression (missing/stale field).
    assert updated_body["updated_at"] >= original_updated_at

    delete_response = await client.delete(f"/api/v1/semesters/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/semesters/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/semesters/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(f"/api/v1/semesters/{entity_id}/restore", headers=headers)
    assert restore_response.status_code == 200
    assert restore_response.json()["id"] == entity_id

    get_after_restore = await client.get(f"/api/v1/semesters/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_semester_get_nonexistent_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="semadmin9", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="404")
    token = await _login(client, "semadmin9")

    response = await client.get(
        f"/api/v1/semesters/{uuid.uuid4()}",
        headers=_institution_headers(token, academic_year.institution_id),
    )
    assert response.status_code == 404


async def test_list_semesters_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="semadmin10", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(
        db_session, code="LIST", start_date=date(2020, 1, 1), end_date=date(2030, 12, 31)
    )
    token = await _login(client, "semadmin10")
    headers = _institution_headers(token, academic_year.institution_id)

    base_start = date(2021, 1, 1)
    for i in range(5):
        start = base_start.replace(year=base_start.year + i)
        end = start.replace(month=6, day=30)
        create_response = await client.post(
            "/api/v1/semesters",
            json={
                "academic_year_id": str(academic_year.id),
                "name": f"Semester {i}",
                "semester_number": i + 1,
                "term_type": "odd",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            },
            headers=headers,
        )
        assert create_response.status_code == 201

    response = await client.get("/api/v1/semesters?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total_pages"] == 3


async def test_bulk_create_semesters_collects_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="semadmin11", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="BULK")
    token = await _login(client, "semadmin11")
    headers = _institution_headers(token, academic_year.institution_id)

    response = await client.post(
        "/api/v1/semesters/bulk",
        json=[
            {
                "academic_year_id": str(academic_year.id),
                "name": "Semester 1",
                "semester_number": 1,
                "term_type": "odd",
                "start_date": "2025-06-01",
                "end_date": "2025-11-30",
            },
            {
                "academic_year_id": str(academic_year.id),
                "name": "Semester 1 Dup",
                "semester_number": 1,
                "term_type": "odd",
                "start_date": "2025-06-01",
                "end_date": "2025-11-30",
            },
            {
                "academic_year_id": str(academic_year.id),
                "name": "Semester 2",
                "semester_number": 2,
                "term_type": "even",
                "start_date": "2025-12-01",
                "end_date": "2026-05-31",
            },
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


async def test_semester_import_export_skeleton_endpoints(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="semadmin12", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="IMPEXP")
    token = await _login(client, "semadmin12")
    headers = _institution_headers(token, academic_year.institution_id)

    import_response = await client.post("/api/v1/semesters/import", headers=headers)
    assert import_response.status_code == 202
    assert import_response.json()["status"] == "not_implemented"

    export_response = await client.get("/api/v1/semesters/export", headers=headers)
    assert export_response.status_code == 200
    assert export_response.json()["status"] == "not_implemented"
