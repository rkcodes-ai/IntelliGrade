"""Rubric management API tests: CRUD, tenancy, template vs. question-bound, versioning."""

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bloom_taxonomy_level import BloomTaxonomyLevel
from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.difficulty_level import DifficultyLevel
from app.models.institution import Institution
from app.models.program import Program
from app.models.question import Question
from app.models.question_category import QuestionCategory
from app.models.question_type import QuestionType
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


async def _create_institution(db_session: AsyncSession, *, code: str) -> Institution:
    institution = Institution(
        name=f"Institution {code}", code=f"I-{code}", institution_type="university", is_active=True
    )
    db_session.add(institution)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(institution)
    return institution


async def _create_question(db_session: AsyncSession, *, code: str) -> Question:
    """
    Builds the full Institution->Campus->Department->Program->Course->
    SubjectCategory->Subject->lookup-rows->Question parent chain via direct
    ORM inserts, adapted from `tests/test_questions_api.py`'s helper (see
    that file's module docstring for why the Module 04 lookup tables'
    shape is assumed rather than imported from a schema definition).
    """
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

    category = QuestionCategory(
        institution_id=institution.id, code=f"QC-{code}", name=f"Category {code}"
    )
    question_type = QuestionType(
        institution_id=institution.id, code=f"QT-{code}", name=f"Type {code}"
    )
    difficulty = DifficultyLevel(
        institution_id=institution.id, code=f"DL-{code}", name=f"Difficulty {code}", level_order=1
    )
    bloom = BloomTaxonomyLevel(
        institution_id=institution.id, code=f"BL-{code}", name=f"Bloom {code}", level_order=1
    )
    db_session.add_all([category, question_type, difficulty, bloom])
    await db_session.flush()

    question = Question(
        institution_id=institution.id,
        subject_id=subject.id,
        question_category_id=category.id,
        question_type_id=question_type.id,
        difficulty_level_id=difficulty.id,
        bloom_level_id=bloom.id,
        question_text=f"What is {code}?",
        marks=Decimal("5.00"),
    )
    db_session.add(question)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(question)
    return question


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"name": "Essay Rubric", "total_marks": "20.00"}
    payload.update(overrides)
    return payload


async def test_create_rubric_template_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="radmin1", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="CREATE")
    token = await _login(client, "radmin1")

    response = await client.post(
        "/api/v1/rubrics",
        json=_payload(),
        headers=_institution_headers(token, institution.id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Essay Rubric"
    assert body["total_marks"] == "20.00"
    assert body["question_id"] is None
    assert body["is_active"] is True
    assert body["current_version"] == 1


async def test_create_rubric_with_question_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="radmin2", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="WITHQ")
    token = await _login(client, "radmin2")

    response = await client.post(
        "/api/v1/rubrics",
        json=_payload(question_id=str(question.id)),
        headers=_institution_headers(token, question.institution_id),
    )

    assert response.status_code == 201
    assert response.json()["question_id"] == str(question.id)


async def test_create_rubric_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="radmin3", role=seed_rbac["super_admin"])
    await _create_institution(db_session, code="NOHEADER")
    token = await _login(client, "radmin3")

    response = await client.post("/api/v1/rubrics", json=_payload(), headers=auth_headers(token))

    assert response.status_code == 422


async def test_create_rubric_rejects_nonexistent_question(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="radmin4", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="BADQ")
    token = await _login(client, "radmin4")

    response = await client.post(
        "/api/v1/rubrics",
        json=_payload(question_id=str(uuid.uuid4())),
        headers=_institution_headers(token, institution.id),
    )

    assert response.status_code == 404


async def test_non_privileged_role_cannot_create_rubric(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rstudent1", role=seed_rbac["student"])
    institution = await _create_institution(db_session, code="FORBIDDEN")
    token = await _login(client, "rstudent1")

    response = await client.post(
        "/api/v1/rubrics",
        json=_payload(),
        headers=_institution_headers(token, institution.id),
    )

    assert response.status_code == 403


async def test_get_nonexistent_rubric_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="radmin5", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="GETMISSING")
    token = await _login(client, "radmin5")

    response = await client.get(
        f"/api/v1/rubrics/{uuid.uuid4()}",
        headers=_institution_headers(token, institution.id),
    )

    assert response.status_code == 404


async def test_rubric_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="radmin6", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="ROUNDTRIP")
    token = await _login(client, "radmin6")
    headers = _institution_headers(token, institution.id)

    created = await client.post("/api/v1/rubrics", json=_payload(), headers=headers)
    assert created.status_code == 201
    entity_id = created.json()["id"]
    original_updated_at = created.json()["updated_at"]

    get_response = await client.get(f"/api/v1/rubrics/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Essay Rubric"

    # A cosmetic-only change (is_active) must NOT bump current_version.
    cosmetic_update = await client.patch(
        f"/api/v1/rubrics/{entity_id}", json={"is_active": False}, headers=headers
    )
    assert cosmetic_update.status_code == 200
    assert cosmetic_update.json()["is_active"] is False
    assert cosmetic_update.json()["current_version"] == 1

    # A content change (total_marks) must bump current_version.
    update_response = await client.patch(
        f"/api/v1/rubrics/{entity_id}", json={"total_marks": "25.00"}, headers=headers
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert updated_body["total_marks"] == "25.00"
    assert updated_body["current_version"] == 2
    # SQLite's func.now() is whole-second resolution -- use >=, not !=.
    assert updated_body["updated_at"] >= original_updated_at

    delete_response = await client.delete(f"/api/v1/rubrics/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/rubrics/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/rubrics/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(f"/api/v1/rubrics/{entity_id}/restore", headers=headers)
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/rubrics/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_list_rubrics_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="radmin7", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="LIST")
    token = await _login(client, "radmin7")
    headers = _institution_headers(token, institution.id)

    for i in range(5):
        response = await client.post(
            "/api/v1/rubrics", json=_payload(name=f"Rubric {i}"), headers=headers
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/rubrics?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_rubrics_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="radmin8", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="BULK")
    token = await _login(client, "radmin8")
    headers = _institution_headers(token, institution.id)

    response = await client.post(
        "/api/v1/rubrics/bulk",
        json=[
            _payload(name="Bulk One"),
            _payload(name="Bulk Bad", question_id=str(uuid.uuid4())),
            _payload(name="Bulk Two"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


async def test_export_rubrics_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="radmin9", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="EXPORT")
    token = await _login(client, "radmin9")
    headers = _institution_headers(token, institution.id)

    response = await client.get("/api/v1/rubrics/export", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_rubrics_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="radmin10", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="IMPORT")
    token = await _login(client, "radmin10")
    headers = _institution_headers(token, institution.id)

    response = await client.post("/api/v1/rubrics/import", headers=headers)

    assert response.status_code == 202
    assert response.json()["status"] == "not_implemented"
