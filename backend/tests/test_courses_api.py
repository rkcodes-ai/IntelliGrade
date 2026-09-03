"""Course management API tests: CRUD, tenancy, and parent-FK/uniqueness business rules."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campus import Campus
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


async def _create_program(db_session: AsyncSession, *, code: str = "PROG1") -> Program:
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
    await db_session.commit()
    await db_session.refresh(program)
    return program


def _institution_headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


async def test_create_course_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="courseadmin1", role=seed_rbac["super_admin"])
    program = await _create_program(db_session, code="CREATE")
    token = await _login(client, "courseadmin1")

    response = await client.post(
        "/api/v1/courses",
        json={
            "program_id": str(program.id),
            "name": "Computer Science Engineering",
            "code": "CSE",
        },
        headers=_institution_headers(token, program.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Computer Science Engineering"
    assert body["code"] == "CSE"
    assert body["program_id"] == str(program.id)
    assert body["is_active"] is True


async def test_create_course_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="courseadmin2", role=seed_rbac["super_admin"])
    program = await _create_program(db_session, code="NOHEADER")
    token = await _login(client, "courseadmin2")

    response = await client.post(
        "/api/v1/courses",
        json={"program_id": str(program.id), "name": "Course", "code": "C1"},
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_course_rejects_duplicate_code_within_program(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="courseadmin3", role=seed_rbac["super_admin"])
    program = await _create_program(db_session, code="DUPE")
    token = await _login(client, "courseadmin3")
    headers = _institution_headers(token, program.institution_id)

    first = await client.post(
        "/api/v1/courses",
        json={"program_id": str(program.id), "name": "Course One", "code": "C1"},
        headers=headers,
    )
    assert first.status_code == 201

    duplicate = await client.post(
        "/api/v1/courses",
        json={"program_id": str(program.id), "name": "Course One Duplicate", "code": "C1"},
        headers=headers,
    )
    assert duplicate.status_code == 409


async def test_create_course_rejects_nonexistent_program(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="courseadmin4", role=seed_rbac["super_admin"])
    program = await _create_program(db_session, code="BADPARENT")
    token = await _login(client, "courseadmin4")

    response = await client.post(
        "/api/v1/courses",
        json={"program_id": str(uuid.uuid4()), "name": "Course", "code": "C1"},
        headers=_institution_headers(token, program.institution_id),
    )

    assert response.status_code == 404


async def test_non_privileged_role_cannot_create_course(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="coursestudent1", role=seed_rbac["student"])
    program = await _create_program(db_session, code="FORBIDDEN")
    token = await _login(client, "coursestudent1")

    response = await client.post(
        "/api/v1/courses",
        json={"program_id": str(program.id), "name": "Course", "code": "C1"},
        headers=_institution_headers(token, program.institution_id),
    )

    assert response.status_code == 403


async def test_course_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="courseadmin5", role=seed_rbac["super_admin"])
    program = await _create_program(db_session, code="ROUNDTRIP")
    token = await _login(client, "courseadmin5")
    headers = _institution_headers(token, program.institution_id)

    create_response = await client.post(
        "/api/v1/courses",
        json={"program_id": str(program.id), "name": "Course One", "code": "C1"},
        headers=headers,
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]

    get_response = await client.get(f"/api/v1/courses/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["code"] == "C1"

    update_response = await client.patch(
        f"/api/v1/courses/{entity_id}", json={"name": "Updated Course Name"}, headers=headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Course Name"

    delete_response = await client.delete(f"/api/v1/courses/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/courses/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/courses/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(f"/api/v1/courses/{entity_id}/restore", headers=headers)
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/courses/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_list_courses_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="courseadmin6", role=seed_rbac["super_admin"])
    program = await _create_program(db_session, code="LIST")
    token = await _login(client, "courseadmin6")
    headers = _institution_headers(token, program.institution_id)

    for i in range(5):
        create_response = await client.post(
            "/api/v1/courses",
            json={"program_id": str(program.id), "name": f"Course {i}", "code": f"C{i}"},
            headers=headers,
        )
        assert create_response.status_code == 201

    response = await client.get("/api/v1/courses?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_courses_collects_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="courseadmin7", role=seed_rbac["super_admin"])
    program = await _create_program(db_session, code="BULK")
    token = await _login(client, "courseadmin7")
    headers = _institution_headers(token, program.institution_id)

    response = await client.post(
        "/api/v1/courses/bulk",
        json=[
            {"program_id": str(program.id), "name": "Course One", "code": "B1"},
            {"program_id": str(program.id), "name": "Course One Dup", "code": "B1"},
            {"program_id": str(program.id), "name": "Course Two", "code": "B2"},
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


async def test_course_import_export_skeleton_endpoints(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="courseadmin8", role=seed_rbac["super_admin"])
    program = await _create_program(db_session, code="IMPEXP")
    token = await _login(client, "courseadmin8")
    headers = _institution_headers(token, program.institution_id)

    import_response = await client.post("/api/v1/courses/import", headers=headers)
    assert import_response.status_code == 202
    assert import_response.json()["status"] == "not_implemented"

    export_response = await client.get("/api/v1/courses/export", headers=headers)
    assert export_response.status_code == 200
    assert export_response.json()["status"] == "not_implemented"
