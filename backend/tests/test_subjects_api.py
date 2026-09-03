"""Subject management API tests: CRUD, tenancy, and parent-FK/uniqueness business rules."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.institution import Institution
from app.models.program import Program
from app.models.subject_category import SubjectCategory
from tests.conftest import auth_headers, create_test_user


async def _login(client: AsyncClient, username: str, password: str = "CorrectHorse9!") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def _create_course_and_category(
    db_session: AsyncSession, *, code: str = "SUB1"
) -> tuple[Course, SubjectCategory]:
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

    category = SubjectCategory(
        institution_id=institution.id, code=f"CAT-{code}", name=f"Category {code}"
    )
    db_session.add(category)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(course)
    await db_session.refresh(category)
    return course, category


def _institution_headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


def _payload(
    course_id: uuid.UUID, category_id: uuid.UUID, **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "course_id": str(course_id),
        "subject_category_id": str(category_id),
        "code": "CS101",
        "name": "Data Structures",
        "credits": 4.0,
        "semester_number": 3,
    }
    payload.update(overrides)
    return payload


async def test_create_subject_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="subjadmin1", role=seed_rbac["super_admin"])
    course, category = await _create_course_and_category(db_session, code="CREATE")
    token = await _login(client, "subjadmin1")

    response = await client.post(
        "/api/v1/subjects",
        json=_payload(course.id, category.id),
        headers=_institution_headers(token, course.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "CS101"
    assert body["name"] == "Data Structures"
    assert body["course_id"] == str(course.id)
    assert body["subject_category_id"] == str(category.id)
    assert float(body["credits"]) == 4.0
    assert body["semester_number"] == 3
    assert body["is_active"] is True


async def test_create_subject_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="subjadmin2", role=seed_rbac["super_admin"])
    course, category = await _create_course_and_category(db_session, code="NOHEADER")
    token = await _login(client, "subjadmin2")

    response = await client.post(
        "/api/v1/subjects", json=_payload(course.id, category.id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_subject_rejects_duplicate_code(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="subjadmin3", role=seed_rbac["super_admin"])
    course, category = await _create_course_and_category(db_session, code="DUPE")
    token = await _login(client, "subjadmin3")
    headers = _institution_headers(token, course.institution_id)

    first = await client.post(
        "/api/v1/subjects", json=_payload(course.id, category.id), headers=headers
    )
    assert first.status_code == 201

    duplicate = await client.post(
        "/api/v1/subjects",
        json=_payload(course.id, category.id, name="Data Structures 2"),
        headers=headers,
    )
    assert duplicate.status_code == 409


async def test_create_subject_rejects_nonexistent_course(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="subjadmin4", role=seed_rbac["super_admin"])
    course, category = await _create_course_and_category(db_session, code="BADCOURSE")
    token = await _login(client, "subjadmin4")

    response = await client.post(
        "/api/v1/subjects",
        json=_payload(uuid.uuid4(), category.id),
        headers=_institution_headers(token, course.institution_id),
    )

    assert response.status_code == 404


async def test_create_subject_rejects_nonexistent_category(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="subjadmin5", role=seed_rbac["super_admin"])
    course, category = await _create_course_and_category(db_session, code="BADCAT")
    token = await _login(client, "subjadmin5")

    response = await client.post(
        "/api/v1/subjects",
        json=_payload(course.id, uuid.uuid4()),
        headers=_institution_headers(token, course.institution_id),
    )

    assert response.status_code == 404


async def test_create_subject_rejects_zero_credits(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="subjadmin6", role=seed_rbac["super_admin"])
    course, category = await _create_course_and_category(db_session, code="ZEROCREDIT")
    token = await _login(client, "subjadmin6")

    response = await client.post(
        "/api/v1/subjects",
        json=_payload(course.id, category.id, credits=0),
        headers=_institution_headers(token, course.institution_id),
    )

    assert response.status_code == 422


async def test_create_subject_rejects_invalid_semester_number(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="subjadmin7", role=seed_rbac["super_admin"])
    course, category = await _create_course_and_category(db_session, code="BADSEM")
    token = await _login(client, "subjadmin7")

    response = await client.post(
        "/api/v1/subjects",
        json=_payload(course.id, category.id, semester_number=21),
        headers=_institution_headers(token, course.institution_id),
    )

    assert response.status_code == 422


async def test_non_privileged_role_cannot_create_subject(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="subjstudent1", role=seed_rbac["student"])
    course, category = await _create_course_and_category(db_session, code="FORBIDDEN")
    token = await _login(client, "subjstudent1")

    response = await client.post(
        "/api/v1/subjects",
        json=_payload(course.id, category.id),
        headers=_institution_headers(token, course.institution_id),
    )

    assert response.status_code == 403


async def test_subject_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="subjadmin8", role=seed_rbac["super_admin"])
    course, category = await _create_course_and_category(db_session, code="ROUNDTRIP")
    token = await _login(client, "subjadmin8")
    headers = _institution_headers(token, course.institution_id)

    create_response = await client.post(
        "/api/v1/subjects", json=_payload(course.id, category.id), headers=headers
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]

    get_response = await client.get(f"/api/v1/subjects/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["code"] == "CS101"

    update_response = await client.patch(
        f"/api/v1/subjects/{entity_id}", json={"name": "Updated Subject Name"}, headers=headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Subject Name"
    assert update_response.json()["updated_at"] is not None

    delete_response = await client.delete(f"/api/v1/subjects/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/subjects/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/subjects/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(f"/api/v1/subjects/{entity_id}/restore", headers=headers)
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/subjects/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_list_subjects_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="subjadmin9", role=seed_rbac["super_admin"])
    course, category = await _create_course_and_category(db_session, code="LIST")
    token = await _login(client, "subjadmin9")
    headers = _institution_headers(token, course.institution_id)

    for i in range(5):
        create_response = await client.post(
            "/api/v1/subjects",
            json=_payload(course.id, category.id, code=f"CS10{i}", name=f"Subject {i}"),
            headers=headers,
        )
        assert create_response.status_code == 201

    response = await client.get("/api/v1/subjects?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_subjects_collects_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="subjadmin10", role=seed_rbac["super_admin"])
    course, category = await _create_course_and_category(db_session, code="BULK")
    token = await _login(client, "subjadmin10")
    headers = _institution_headers(token, course.institution_id)

    response = await client.post(
        "/api/v1/subjects/bulk",
        json=[
            _payload(course.id, category.id, code="B1"),
            _payload(course.id, category.id, code="B1"),
            _payload(course.id, category.id, code="B2"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


async def test_subject_import_export_skeleton_endpoints(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="subjadmin11", role=seed_rbac["super_admin"])
    course, _category = await _create_course_and_category(db_session, code="IMPEXP")
    token = await _login(client, "subjadmin11")
    headers = _institution_headers(token, course.institution_id)

    import_response = await client.post("/api/v1/subjects/import", headers=headers)
    assert import_response.status_code == 202
    assert import_response.json()["status"] == "not_implemented"

    export_response = await client.get("/api/v1/subjects/export", headers=headers)
    assert export_response.status_code == 200
    assert export_response.json()["status"] == "not_implemented"
