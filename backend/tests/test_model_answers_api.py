"""ModelAnswer management API tests: CRUD, tenancy, multiple-per-parent.

`Question` and `AnswerKey` and their full parent chain are built directly via
the ORM (mirroring `test_questions_api.py`'s helper pattern) since they are
parent-chain scaffolding here, not the entity under test.
"""

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer_key import AnswerKey
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


async def _create_question(db_session: AsyncSession, *, code: str) -> Question:
    """Builds the full Module 03/04 parent chain and returns a persisted `Question`."""
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
        question_text=f"Question {code}?",
        marks=Decimal("5.00"),
        language="en",
        approval_status="draft",
        current_version=1,
        is_active=True,
    )
    db_session.add(question)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(question)
    return question


async def _create_answer_key(db_session: AsyncSession, *, code: str) -> AnswerKey:
    """Builds the full parent chain and returns a persisted `AnswerKey`."""
    question = await _create_question(db_session, code=code)
    answer_key = AnswerKey(
        institution_id=question.institution_id,
        question_id=question.id,
        reference_answer=f"Reference answer {code}",
        current_version=1,
    )
    db_session.add(answer_key)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(answer_key)
    return answer_key


def _payload(answer_key_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "answer_key_id": str(answer_key_id),
        "content": "A correct model answer for band A.",
    }
    payload.update(overrides)
    return payload


async def test_create_model_answer_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="madmin1", role=seed_rbac["super_admin"])
    answer_key = await _create_answer_key(db_session, code="CREATE")
    token = await _login(client, "madmin1")

    response = await client.post(
        "/api/v1/model-answers",
        json=_payload(answer_key.id, marks_allocated=3.5, display_order=1),
        headers=_institution_headers(token, answer_key.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["answer_key_id"] == str(answer_key.id)
    assert body["content"] == "A correct model answer for band A."
    assert float(body["marks_allocated"]) == 3.5
    assert body["display_order"] == 1


async def test_create_model_answer_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="madmin2", role=seed_rbac["super_admin"])
    answer_key = await _create_answer_key(db_session, code="NOHEADER")
    token = await _login(client, "madmin2")

    response = await client.post(
        "/api/v1/model-answers", json=_payload(answer_key.id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_model_answer_rejects_nonexistent_answer_key(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="madmin3", role=seed_rbac["super_admin"])
    answer_key = await _create_answer_key(db_session, code="BADPARENT")
    token = await _login(client, "madmin3")

    response = await client.post(
        "/api/v1/model-answers",
        json=_payload(uuid.uuid4()),
        headers=_institution_headers(token, answer_key.institution_id),
    )

    assert response.status_code == 404


async def test_non_privileged_role_cannot_create_model_answer(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="mstudent1", role=seed_rbac["student"])
    answer_key = await _create_answer_key(db_session, code="FORBIDDEN")
    token = await _login(client, "mstudent1")

    response = await client.post(
        "/api/v1/model-answers",
        json=_payload(answer_key.id),
        headers=_institution_headers(token, answer_key.institution_id),
    )

    assert response.status_code == 403


async def test_get_nonexistent_model_answer_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="madmin4", role=seed_rbac["super_admin"])
    answer_key = await _create_answer_key(db_session, code="GETMISSING")
    token = await _login(client, "madmin4")

    response = await client.get(
        f"/api/v1/model-answers/{uuid.uuid4()}",
        headers=_institution_headers(token, answer_key.institution_id),
    )

    assert response.status_code == 404


async def test_model_answer_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="madmin5", role=seed_rbac["super_admin"])
    answer_key = await _create_answer_key(db_session, code="ROUNDTRIP")
    token = await _login(client, "madmin5")
    headers = _institution_headers(token, answer_key.institution_id)

    created = await client.post(
        "/api/v1/model-answers", json=_payload(answer_key.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    created_updated_at = created.json()["updated_at"]

    get_response = await client.get(f"/api/v1/model-answers/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["content"] == "A correct model answer for band A."

    update_response = await client.patch(
        f"/api/v1/model-answers/{entity_id}",
        json={"content": "Updated model answer content.", "display_order": 2},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["content"] == "Updated model answer content."
    assert update_response.json()["display_order"] == 2
    # SQLite's func.now() is whole-second resolution -- use >=, not !=.
    assert update_response.json()["updated_at"] >= created_updated_at

    delete_response = await client.delete(f"/api/v1/model-answers/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/model-answers/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/model-answers/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/model-answers/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/model-answers/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_list_model_answers_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="madmin6", role=seed_rbac["super_admin"])
    answer_key = await _create_answer_key(db_session, code="LIST")
    token = await _login(client, "madmin6")
    headers = _institution_headers(token, answer_key.institution_id)

    for i in range(5):
        response = await client.post(
            "/api/v1/model-answers",
            json=_payload(answer_key.id, content=f"Model answer {i}", display_order=i),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/model-answers?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_model_answers_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="mabulk1", role=seed_rbac["super_admin"])
    answer_key = await _create_answer_key(db_session, code="BULK")
    token = await _login(client, "mabulk1")
    headers = _institution_headers(token, answer_key.institution_id)

    response = await client.post(
        "/api/v1/model-answers/bulk",
        json=[
            _payload(answer_key.id, content="Model answer one"),
            _payload(answer_key.id, content="Model answer two"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert body["errors"] == []


async def test_bulk_create_model_answers_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="mabulk2", role=seed_rbac["super_admin"])
    answer_key = await _create_answer_key(db_session, code="BULKERR")
    token = await _login(client, "mabulk2")
    headers = _institution_headers(token, answer_key.institution_id)
    bad_answer_key_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/model-answers/bulk",
        json=[
            _payload(answer_key.id, content="Valid model answer"),
            _payload(bad_answer_key_id, content="Orphan model answer"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["index"] == 1
    assert body["errors"][0]["answer_key_id"] == str(bad_answer_key_id)


async def test_export_model_answers_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="maexport1", role=seed_rbac["super_admin"])
    token = await _login(client, "maexport1")

    response = await client.get("/api/v1/model-answers/export", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_model_answers_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="maimport1", role=seed_rbac["super_admin"])
    token = await _login(client, "maimport1")

    response = await client.post("/api/v1/model-answers/import", headers=auth_headers(token))

    assert response.status_code == 202
    assert response.json()["status"] == "not_implemented"
