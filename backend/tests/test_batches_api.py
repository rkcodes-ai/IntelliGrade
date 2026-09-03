"""Batch management API tests: CRUD, tenancy, and parent-FK/uniqueness business rules."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.institution import Institution
from app.models.program import Program
from tests.conftest import auth_headers, create_test_user


async def _login(client: AsyncClient, username: str, password: str = "CorrectHorse9!") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def _create_course(db_session: AsyncSession, *, code: str = "BATCH1") -> Course:
    institution = Institution(
        name=f"Institution {code}", code=f"I-{code}", institution_type="university", is_active=True
    )
    db_session.add(institution)
    await db_session.flush()

    campus = Campus(institution_id=institution.id, name=f"Campus {code}", code=f"C-{code}")
    db_session.add(campus)
    await db_session.flush()

    department = Department(
        institution_id=institution.id, campus_id=campus.id, name=f"Dept {code}", code=f"D-{code}"
    )
    db_session.add(department)
    await db_session.flush()

    program = Program(
        institution_id=institution.id,
        department_id=department.id,
        name=f"Program {code}",
        code=f"P-{code}",
        degree_type="ug",
        duration_years=4,
        total_semesters=8,
    )
    db_session.add(program)
    await db_session.flush()

    course = Course(
        institution_id=institution.id,
        program_id=program.id,
        name=f"Course {code}",
        code=f"CO-{code}",
    )
    db_session.add(course)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(course)
    return course


def _institution_headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


async def test_create_batch_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="batchadmin1", role=seed_rbac["super_admin"])
    course = await _create_course(db_session, code="CREATE")
    token = await _login(client, "batchadmin1")

    response = await client.post(
        "/api/v1/batches",
        json={
            "course_id": str(course.id),
            "name": "2024-2028",
            "start_year": 2024,
            "end_year": 2028,
        },
        headers=_institution_headers(token, course.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "2024-2028"
    assert body["start_year"] == 2024
    assert body["end_year"] == 2028
    assert body["course_id"] == str(course.id)
    assert body["is_active"] is True
    assert body["current_semester_number"] == 1


async def test_create_batch_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="batchadmin2", role=seed_rbac["super_admin"])
    course = await _create_course(db_session, code="NOHEADER")
    token = await _login(client, "batchadmin2")

    response = await client.post(
        "/api/v1/batches",
        json={
            "course_id": str(course.id),
            "name": "2024-2028",
            "start_year": 2024,
            "end_year": 2028,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_batch_rejects_duplicate_name_within_course(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="batchadmin3", role=seed_rbac["super_admin"])
    course = await _create_course(db_session, code="DUPE")
    token = await _login(client, "batchadmin3")
    headers = _institution_headers(token, course.institution_id)

    first = await client.post(
        "/api/v1/batches",
        json={
            "course_id": str(course.id),
            "name": "2024-2028",
            "start_year": 2024,
            "end_year": 2028,
        },
        headers=headers,
    )
    assert first.status_code == 201

    duplicate = await client.post(
        "/api/v1/batches",
        json={
            "course_id": str(course.id),
            "name": "2024-2028",
            "start_year": 2025,
            "end_year": 2029,
        },
        headers=headers,
    )
    assert duplicate.status_code == 409


async def test_create_batch_rejects_nonexistent_course(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="batchadmin4", role=seed_rbac["super_admin"])
    course = await _create_course(db_session, code="BADPARENT")
    token = await _login(client, "batchadmin4")

    response = await client.post(
        "/api/v1/batches",
        json={
            "course_id": str(uuid.uuid4()),
            "name": "2024-2028",
            "start_year": 2024,
            "end_year": 2028,
        },
        headers=_institution_headers(token, course.institution_id),
    )

    assert response.status_code == 404


async def test_create_batch_rejects_invalid_year_range(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="batchadmin5", role=seed_rbac["super_admin"])
    course = await _create_course(db_session, code="BADRANGE")
    token = await _login(client, "batchadmin5")

    response = await client.post(
        "/api/v1/batches",
        json={
            "course_id": str(course.id),
            "name": "2028-2024",
            "start_year": 2028,
            "end_year": 2024,
        },
        headers=_institution_headers(token, course.institution_id),
    )

    assert response.status_code == 422


async def test_non_privileged_role_cannot_create_batch(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="batchstudent1", role=seed_rbac["student"])
    course = await _create_course(db_session, code="FORBIDDEN")
    token = await _login(client, "batchstudent1")

    response = await client.post(
        "/api/v1/batches",
        json={
            "course_id": str(course.id),
            "name": "2024-2028",
            "start_year": 2024,
            "end_year": 2028,
        },
        headers=_institution_headers(token, course.institution_id),
    )

    assert response.status_code == 403


async def test_batch_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="batchadmin6", role=seed_rbac["super_admin"])
    course = await _create_course(db_session, code="ROUNDTRIP")
    token = await _login(client, "batchadmin6")
    headers = _institution_headers(token, course.institution_id)

    create_response = await client.post(
        "/api/v1/batches",
        json={
            "course_id": str(course.id),
            "name": "2024-2028",
            "start_year": 2024,
            "end_year": 2028,
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]
    original_updated_at = create_response.json()["updated_at"]

    get_response = await client.get(f"/api/v1/batches/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "2024-2028"

    update_response = await client.patch(
        f"/api/v1/batches/{entity_id}",
        json={"max_strength": 120, "current_semester_number": 2},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert updated_body["max_strength"] == 120
    assert updated_body["current_semester_number"] == 2
    assert "updated_at" in updated_body
    # SQLite's func.now() has only whole-second resolution (unlike
    # PostgreSQL's microsecond precision in production), so a fast
    # create-then-update in the same test can legitimately land in the same
    # second — assert non-decreasing, not strict inequality, to avoid
    # flakiness while still catching a regression (missing/stale field).
    assert updated_body["updated_at"] >= original_updated_at

    delete_response = await client.delete(f"/api/v1/batches/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/batches/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/batches/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(f"/api/v1/batches/{entity_id}/restore", headers=headers)
    assert restore_response.status_code == 200
    assert restore_response.json()["id"] == entity_id

    get_after_restore = await client.get(f"/api/v1/batches/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_batch_get_nonexistent_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="batchadmin7", role=seed_rbac["super_admin"])
    course = await _create_course(db_session, code="404")
    token = await _login(client, "batchadmin7")

    response = await client.get(
        f"/api/v1/batches/{uuid.uuid4()}",
        headers=_institution_headers(token, course.institution_id),
    )
    assert response.status_code == 404


async def test_list_batches_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="batchadmin8", role=seed_rbac["super_admin"])
    course = await _create_course(db_session, code="LIST")
    token = await _login(client, "batchadmin8")
    headers = _institution_headers(token, course.institution_id)

    for i in range(5):
        create_response = await client.post(
            "/api/v1/batches",
            json={
                "course_id": str(course.id),
                "name": f"202{i}-202{i+4}",
                "start_year": 2020 + i,
                "end_year": 2024 + i,
            },
            headers=headers,
        )
        assert create_response.status_code == 201

    response = await client.get("/api/v1/batches?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_batches_collects_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="batchadmin9", role=seed_rbac["super_admin"])
    course = await _create_course(db_session, code="BULK")
    token = await _login(client, "batchadmin9")
    headers = _institution_headers(token, course.institution_id)

    response = await client.post(
        "/api/v1/batches/bulk",
        json=[
            {
                "course_id": str(course.id),
                "name": "2024-2028",
                "start_year": 2024,
                "end_year": 2028,
            },
            {
                "course_id": str(course.id),
                "name": "2024-2028",
                "start_year": 2025,
                "end_year": 2029,
            },
            {
                "course_id": str(course.id),
                "name": "2030-2034",
                "start_year": 2030,
                "end_year": 2034,
            },
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


async def test_batch_import_export_skeleton_endpoints(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="batchadmin10", role=seed_rbac["super_admin"])
    course = await _create_course(db_session, code="IMPEXP")
    token = await _login(client, "batchadmin10")
    headers = _institution_headers(token, course.institution_id)

    import_response = await client.post("/api/v1/batches/import", headers=headers)
    assert import_response.status_code == 202
    assert import_response.json()["status"] == "not_implemented"

    export_response = await client.get("/api/v1/batches/export", headers=headers)
    assert export_response.status_code == 200
    assert export_response.json()["status"] == "not_implemented"
