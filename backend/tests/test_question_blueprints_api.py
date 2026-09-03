"""QuestionBlueprint API tests: CRUD, tenancy, versioning, soft-delete/restore."""

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.institution import Institution
from app.models.program import Program
from app.models.subject import Subject
from app.models.subject_category import SubjectCategory
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


async def _create_subject(db_session: AsyncSession, *, code: str) -> Subject:
    """Builds the full Module 03 parent chain a `QuestionBlueprint` needs and
    returns the `Subject`, mirroring `tests/test_questions_api.py`'s
    `_create_subject` helper."""
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

    subject_category = SubjectCategory(
        institution_id=institution.id, code=f"CAT-{code}", name=f"Category {code}"
    )
    db_session.add(subject_category)
    await db_session.flush()

    subject = Subject(
        institution_id=institution.id,
        course_id=course.id,
        subject_category_id=subject_category.id,
        code=f"SUB-{code}",
        name=f"Subject {code}",
        credits=Decimal("4.0"),
        semester_number=1,
    )
    db_session.add(subject)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(subject)
    return subject


async def _create_second_subject(
    db_session: AsyncSession, subject: Subject, *, code: str
) -> Subject:
    """A second `Subject` in the same institution (reusing `course_id`/
    `subject_category_id`), so update tests can PATCH `subject_id` to a
    different-but-still-valid parent within the same tenant."""
    second = Subject(
        institution_id=subject.institution_id,
        course_id=subject.course_id,
        subject_category_id=subject.subject_category_id,
        code=f"SUB-{code}",
        name=f"Subject {code}",
        credits=Decimal("4.0"),
        semester_number=1,
    )
    db_session.add(second)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(second)
    return second


def _payload(subject_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "subject_id": str(subject_id),
        "name": "Midterm Blueprint",
        "total_marks": "100.00",
        "total_questions": 20,
    }
    payload.update(overrides)
    return payload


async def test_create_question_blueprint_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bpadmin1", role=seed_rbac["super_admin"])
    subject = await _create_subject(db_session, code="CREATE")
    token = await _login(client, "bpadmin1")

    response = await client.post(
        "/api/v1/question-blueprints",
        json=_payload(subject.id),
        headers=_institution_headers(token, subject.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["subject_id"] == str(subject.id)
    assert body["name"] == "Midterm Blueprint"
    assert body["total_questions"] == 20
    assert float(body["total_marks"]) == 100.0
    assert body["is_active"] is True
    assert body["current_version"] == 1


async def test_create_question_blueprint_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bpadmin2", role=seed_rbac["super_admin"])
    subject = await _create_subject(db_session, code="NOHEADER")
    token = await _login(client, "bpadmin2")

    response = await client.post(
        "/api/v1/question-blueprints", json=_payload(subject.id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_question_blueprint_rejects_nonexistent_subject(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bpadmin3", role=seed_rbac["super_admin"])
    subject = await _create_subject(db_session, code="BADSUBJECT")
    token = await _login(client, "bpadmin3")

    response = await client.post(
        "/api/v1/question-blueprints",
        json=_payload(uuid.uuid4()),
        headers=_institution_headers(token, subject.institution_id),
    )

    assert response.status_code == 404


async def test_non_privileged_role_cannot_create_question_blueprint(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bpstudent1", role=seed_rbac["student"])
    subject = await _create_subject(db_session, code="FORBIDDEN")
    token = await _login(client, "bpstudent1")

    response = await client.post(
        "/api/v1/question-blueprints",
        json=_payload(subject.id),
        headers=_institution_headers(token, subject.institution_id),
    )

    assert response.status_code == 403


async def test_get_nonexistent_question_blueprint_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bpadmin4", role=seed_rbac["super_admin"])
    subject = await _create_subject(db_session, code="GETMISSING")
    token = await _login(client, "bpadmin4")

    response = await client.get(
        f"/api/v1/question-blueprints/{uuid.uuid4()}",
        headers=_institution_headers(token, subject.institution_id),
    )

    assert response.status_code == 404


async def test_question_blueprint_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bpadmin5", role=seed_rbac["super_admin"])
    subject = await _create_subject(db_session, code="ROUNDTRIP")
    token = await _login(client, "bpadmin5")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/question-blueprints", json=_payload(subject.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    created_updated_at = created.json()["updated_at"]

    get_response = await client.get(f"/api/v1/question-blueprints/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Midterm Blueprint"

    update_response = await client.patch(
        f"/api/v1/question-blueprints/{entity_id}",
        json={"name": "Final Blueprint"},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Final Blueprint"
    # SQLite's func.now() is whole-second resolution -- use >=, not !=.
    assert update_response.json()["updated_at"] >= created_updated_at

    delete_response = await client.delete(
        f"/api/v1/question-blueprints/{entity_id}", headers=headers
    )
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/question-blueprints/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/question-blueprints/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/question-blueprints/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(
        f"/api/v1/question-blueprints/{entity_id}", headers=headers
    )
    assert get_after_restore.status_code == 200


async def test_update_question_blueprint_increments_version_on_marks_or_count_change(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bpadmin6", role=seed_rbac["super_admin"])
    subject = await _create_subject(db_session, code="VERSION")
    token = await _login(client, "bpadmin6")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/question-blueprints", json=_payload(subject.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    assert created.json()["current_version"] == 1

    # A cosmetic field change alone must NOT bump the version counter.
    cosmetic_update = await client.patch(
        f"/api/v1/question-blueprints/{entity_id}",
        json={"name": "Cosmetic rename"},
        headers=headers,
    )
    assert cosmetic_update.status_code == 200
    assert cosmetic_update.json()["current_version"] == 1

    # Changing `total_marks` (the distribution content) must bump it.
    marks_update = await client.patch(
        f"/api/v1/question-blueprints/{entity_id}", json={"total_marks": "150.00"}, headers=headers
    )
    assert marks_update.status_code == 200
    assert marks_update.json()["current_version"] == 2
    assert float(marks_update.json()["total_marks"]) == 150.0


async def test_list_question_blueprints_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bpadmin7", role=seed_rbac["super_admin"])
    subject = await _create_subject(db_session, code="LIST")
    token = await _login(client, "bpadmin7")
    headers = _institution_headers(token, subject.institution_id)

    for i in range(5):
        response = await client.post(
            "/api/v1/question-blueprints",
            json=_payload(subject.id, name=f"Blueprint {i}"),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/question-blueprints?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_question_blueprints_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bpadmin8", role=seed_rbac["super_admin"])
    subject = await _create_subject(db_session, code="BULKOK")
    token = await _login(client, "bpadmin8")
    headers = _institution_headers(token, subject.institution_id)

    response = await client.post(
        "/api/v1/question-blueprints/bulk",
        json=[
            _payload(subject.id, name="Bulk Blueprint One"),
            _payload(subject.id, name="Bulk Blueprint Two"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert body["errors"] == []


async def test_bulk_create_question_blueprints_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bpadmin9", role=seed_rbac["super_admin"])
    subject = await _create_subject(db_session, code="BULKERR")
    token = await _login(client, "bpadmin9")
    headers = _institution_headers(token, subject.institution_id)

    response = await client.post(
        "/api/v1/question-blueprints/bulk",
        json=[
            _payload(subject.id, name="Valid Blueprint"),
            _payload(uuid.uuid4(), name="Missing Subject Blueprint"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1


async def test_export_question_blueprints_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bpadmin10", role=seed_rbac["super_admin"])
    subject = await _create_subject(db_session, code="EXPORT")
    token = await _login(client, "bpadmin10")
    headers = _institution_headers(token, subject.institution_id)

    response = await client.get("/api/v1/question-blueprints/export", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_question_blueprints_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bpadmin11", role=seed_rbac["super_admin"])
    subject = await _create_subject(db_session, code="IMPORT")
    token = await _login(client, "bpadmin11")
    headers = _institution_headers(token, subject.institution_id)

    response = await client.post("/api/v1/question-blueprints/import", headers=headers)

    assert response.status_code == 202
    assert response.json()["status"] == "not_implemented"


async def test_update_question_blueprint_accepts_new_subject_in_same_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bpadmin12", role=seed_rbac["super_admin"])
    subject = await _create_subject(db_session, code="UPDFK")
    other_subject = await _create_second_subject(db_session, subject, code="UPDFK2")
    token = await _login(client, "bpadmin12")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/question-blueprints", json=_payload(subject.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-blueprints/{entity_id}",
        json={"subject_id": str(other_subject.id)},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["subject_id"] == str(other_subject.id)


async def test_update_question_blueprint_rejects_nonexistent_subject(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bpadmin13", role=seed_rbac["super_admin"])
    subject = await _create_subject(db_session, code="UPDBAD")
    token = await _login(client, "bpadmin13")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/question-blueprints", json=_payload(subject.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-blueprints/{entity_id}",
        json={"subject_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404
