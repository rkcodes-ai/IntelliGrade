"""AcademicCalendarEvent API tests: CRUD, tenancy, and date-range business rules."""

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


async def _create_academic_year(db_session: AsyncSession, *, code: str = "AY1") -> AcademicYear:
    institution = Institution(
        name=f"Institution {code}", code=f"I-{code}", institution_type="university", is_active=True
    )
    db_session.add(institution)
    await db_session.flush()

    academic_year = AcademicYear(
        institution_id=institution.id,
        year_label=f"2025-2026-{code}",
        start_date=date(2025, 6, 1),
        end_date=date(2026, 5, 31),
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


def _payload(academic_year_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "academic_year_id": str(academic_year_id),
        "title": "Winter Break",
        "event_type": "holiday",
        "start_date": "2025-12-20",
        "end_date": "2026-01-02",
        "description": "Winter recess",
        "is_holiday": True,
    }
    payload.update(overrides)
    return payload


async def test_create_academic_calendar_event_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="caladmin1", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="CREATE")
    token = await _login(client, "caladmin1")

    response = await client.post(
        "/api/v1/academic-calendar",
        json=_payload(academic_year.id),
        headers=_institution_headers(token, academic_year.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Winter Break"
    assert body["event_type"] == "holiday"
    assert body["is_holiday"] is True
    assert body["academic_year_id"] == str(academic_year.id)


async def test_create_academic_calendar_event_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="caladmin2", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="NOHEADER")
    token = await _login(client, "caladmin2")

    response = await client.post(
        "/api/v1/academic-calendar", json=_payload(academic_year.id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_academic_calendar_event_rejects_nonexistent_academic_year(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="caladmin3", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="BADPARENT")
    token = await _login(client, "caladmin3")

    response = await client.post(
        "/api/v1/academic-calendar",
        json=_payload(uuid.uuid4()),
        headers=_institution_headers(token, academic_year.institution_id),
    )

    assert response.status_code == 404


async def test_create_academic_calendar_event_rejects_start_after_end(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="caladmin4", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="BADDATES")
    token = await _login(client, "caladmin4")

    response = await client.post(
        "/api/v1/academic-calendar",
        json=_payload(academic_year.id, start_date="2026-01-02", end_date="2025-12-20"),
        headers=_institution_headers(token, academic_year.institution_id),
    )

    assert response.status_code == 422


async def test_create_academic_calendar_event_allows_single_day_event(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="caladmin5", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="SINGLEDAY")
    token = await _login(client, "caladmin5")

    response = await client.post(
        "/api/v1/academic-calendar",
        json=_payload(
            academic_year.id, title="Founders Day", start_date="2025-09-01", end_date="2025-09-01"
        ),
        headers=_institution_headers(token, academic_year.institution_id),
    )

    assert response.status_code == 201


async def test_create_academic_calendar_event_rejects_invalid_event_type(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="caladmin6", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="BADTYPE")
    token = await _login(client, "caladmin6")

    response = await client.post(
        "/api/v1/academic-calendar",
        json=_payload(academic_year.id, event_type="festival"),
        headers=_institution_headers(token, academic_year.institution_id),
    )

    assert response.status_code == 422


async def test_non_privileged_role_cannot_create_academic_calendar_event(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="calstudent1", role=seed_rbac["student"])
    academic_year = await _create_academic_year(db_session, code="FORBIDDEN")
    token = await _login(client, "calstudent1")

    response = await client.post(
        "/api/v1/academic-calendar",
        json=_payload(academic_year.id),
        headers=_institution_headers(token, academic_year.institution_id),
    )

    assert response.status_code == 403


async def test_academic_calendar_event_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="caladmin7", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="ROUNDTRIP")
    token = await _login(client, "caladmin7")
    headers = _institution_headers(token, academic_year.institution_id)

    create_response = await client.post(
        "/api/v1/academic-calendar", json=_payload(academic_year.id), headers=headers
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]

    get_response = await client.get(f"/api/v1/academic-calendar/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Winter Break"

    update_response = await client.patch(
        f"/api/v1/academic-calendar/{entity_id}", json={"title": "Updated Title"}, headers=headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Updated Title"
    assert update_response.json()["updated_at"] is not None

    update_bad_dates = await client.patch(
        f"/api/v1/academic-calendar/{entity_id}",
        json={"start_date": "2026-01-02", "end_date": "2025-12-20"},
        headers=headers,
    )
    assert update_bad_dates.status_code == 422

    delete_response = await client.delete(f"/api/v1/academic-calendar/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/academic-calendar/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/academic-calendar/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/academic-calendar/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/academic-calendar/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_list_academic_calendar_events_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="caladmin8", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="LIST")
    token = await _login(client, "caladmin8")
    headers = _institution_headers(token, academic_year.institution_id)

    for i in range(5):
        create_response = await client.post(
            "/api/v1/academic-calendar",
            json=_payload(academic_year.id, title=f"Event {i}"),
            headers=headers,
        )
        assert create_response.status_code == 201

    response = await client.get("/api/v1/academic-calendar?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_academic_calendar_events_collects_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="caladmin9", role=seed_rbac["super_admin"])
    academic_year = await _create_academic_year(db_session, code="BULK")
    token = await _login(client, "caladmin9")
    headers = _institution_headers(token, academic_year.institution_id)

    response = await client.post(
        "/api/v1/academic-calendar/bulk",
        json=[
            _payload(academic_year.id, title="Event A"),
            _payload(
                academic_year.id, title="Event B", start_date="2026-02-02", end_date="2026-01-01"
            ),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1
