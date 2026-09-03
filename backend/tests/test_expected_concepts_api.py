"""
ExpectedConcept management API tests: CRUD, tenancy, exactly-one-of-two-FKs validation.

NOTE: `AnswerKey` (`app.models.answer_key`) is a sibling Module 04 entity built
by another agent in this same implementation wave — see the identical
caveat in `tests/test_expected_keywords_api.py`'s module docstring for the
full rationale behind `_create_answer_key`'s assumed minimal shape.
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
from app.models.rubric import Rubric
from app.models.rubric_criterion import RubricCriterion
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


async def _create_question(db_session: AsyncSession, *, code: str) -> Question:
    """Full Institution->...->Subject->lookup-rows->Question chain (see `test_questions_api.py`)."""
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


async def _create_answer_key(db_session: AsyncSession, *, code: str) -> AnswerKey:
    """See module docstring for the forward-reference caveat on `AnswerKey`'s assumed shape."""
    question = await _create_question(db_session, code=code)
    answer_key = AnswerKey(
        institution_id=question.institution_id,
        question_id=question.id,
        reference_answer="Reference answer",
    )
    db_session.add(answer_key)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(answer_key)
    return answer_key


async def _create_second_criterion(
    db_session: AsyncSession, criterion: RubricCriterion, *, code: str
) -> RubricCriterion:
    """A second `RubricCriterion` (own `Rubric`) in the same institution as
    `criterion`, so update tests can PATCH `rubric_criterion_id` to a
    different-but-still-valid parent within the same tenant."""
    rubric = Rubric(
        institution_id=criterion.institution_id, name=f"Rubric {code}", total_marks=Decimal("20.00")
    )
    db_session.add(rubric)
    await db_session.flush()

    new_criterion = RubricCriterion(
        institution_id=criterion.institution_id,
        rubric_id=rubric.id,
        name=f"Criterion {code}",
        max_marks=Decimal("10.00"),
    )
    db_session.add(new_criterion)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(new_criterion)
    return new_criterion


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"concept_name": "Cellular respiration"}
    payload.update(overrides)
    return payload


async def test_create_expected_concept_with_rubric_criterion_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ecadmin1", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="CREATE")
    token = await _login(client, "ecadmin1")

    response = await client.post(
        "/api/v1/expected-concepts",
        json=_payload(rubric_criterion_id=str(criterion.id)),
        headers=_institution_headers(token, criterion.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["rubric_criterion_id"] == str(criterion.id)
    assert body["answer_key_id"] is None
    assert body["concept_name"] == "Cellular respiration"
    assert body["is_mandatory"] is False


async def test_create_expected_concept_with_answer_key_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ecadmin2", role=seed_rbac["super_admin"])
    answer_key = await _create_answer_key(db_session, code="WITHAK")
    token = await _login(client, "ecadmin2")

    response = await client.post(
        "/api/v1/expected-concepts",
        json=_payload(answer_key_id=str(answer_key.id)),
        headers=_institution_headers(token, answer_key.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["answer_key_id"] == str(answer_key.id)
    assert body["rubric_criterion_id"] is None


async def test_create_expected_concept_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ecadmin3", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="NOHEADER")
    token = await _login(client, "ecadmin3")

    response = await client.post(
        "/api/v1/expected-concepts",
        json=_payload(rubric_criterion_id=str(criterion.id)),
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_expected_concept_rejects_nonexistent_rubric_criterion(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ecadmin4", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="BADCRIT")
    token = await _login(client, "ecadmin4")

    response = await client.post(
        "/api/v1/expected-concepts",
        json=_payload(rubric_criterion_id=str(uuid.uuid4())),
        headers=_institution_headers(token, criterion.institution_id),
    )

    assert response.status_code == 404


async def test_create_expected_concept_rejects_nonexistent_answer_key(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ecadmin5", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="BADAK")
    token = await _login(client, "ecadmin5")

    response = await client.post(
        "/api/v1/expected-concepts",
        json=_payload(answer_key_id=str(uuid.uuid4())),
        headers=_institution_headers(token, criterion.institution_id),
    )

    assert response.status_code == 404


async def test_create_expected_concept_rejects_both_set(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ecadmin6", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="BOTHSET")
    answer_key = await _create_answer_key(db_session, code="BOTHSET2")
    token = await _login(client, "ecadmin6")

    response = await client.post(
        "/api/v1/expected-concepts",
        json=_payload(rubric_criterion_id=str(criterion.id), answer_key_id=str(answer_key.id)),
        headers=_institution_headers(token, criterion.institution_id),
    )

    assert response.status_code == 422


async def test_create_expected_concept_rejects_neither_set(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ecadmin7", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="NEITHER")
    token = await _login(client, "ecadmin7")

    response = await client.post(
        "/api/v1/expected-concepts",
        json=_payload(),
        headers=_institution_headers(token, criterion.institution_id),
    )

    assert response.status_code == 422


async def test_non_privileged_role_cannot_create_expected_concept(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ecstudent1", role=seed_rbac["student"])
    criterion = await _create_criterion(db_session, code="FORBIDDEN")
    token = await _login(client, "ecstudent1")

    response = await client.post(
        "/api/v1/expected-concepts",
        json=_payload(rubric_criterion_id=str(criterion.id)),
        headers=_institution_headers(token, criterion.institution_id),
    )

    assert response.status_code == 403


async def test_get_nonexistent_expected_concept_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ecadmin8", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="GETMISSING")
    token = await _login(client, "ecadmin8")

    response = await client.get(
        f"/api/v1/expected-concepts/{uuid.uuid4()}",
        headers=_institution_headers(token, criterion.institution_id),
    )

    assert response.status_code == 404


async def test_expected_concept_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ecadmin9", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="ROUNDTRIP")
    token = await _login(client, "ecadmin9")
    headers = _institution_headers(token, criterion.institution_id)

    created = await client.post(
        "/api/v1/expected-concepts",
        json=_payload(rubric_criterion_id=str(criterion.id)),
        headers=headers,
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    original_updated_at = created.json()["updated_at"]

    get_response = await client.get(f"/api/v1/expected-concepts/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["concept_name"] == "Cellular respiration"

    update_response = await client.patch(
        f"/api/v1/expected-concepts/{entity_id}",
        json={"is_mandatory": True, "description": "Must mention mitochondria"},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert updated_body["is_mandatory"] is True
    assert updated_body["description"] == "Must mention mitochondria"
    # SQLite's func.now() is whole-second resolution -- use >=, not !=.
    assert updated_body["updated_at"] >= original_updated_at

    delete_response = await client.delete(f"/api/v1/expected-concepts/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/expected-concepts/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/expected-concepts/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/expected-concepts/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/expected-concepts/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_list_expected_concepts_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ecadmin10", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="LIST")
    token = await _login(client, "ecadmin10")
    headers = _institution_headers(token, criterion.institution_id)

    for i in range(5):
        response = await client.post(
            "/api/v1/expected-concepts",
            json=_payload(rubric_criterion_id=str(criterion.id), concept_name=f"Concept {i}"),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/expected-concepts?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_expected_concepts_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ecbulk1", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="BULK")
    token = await _login(client, "ecbulk1")
    headers = _institution_headers(token, criterion.institution_id)

    response = await client.post(
        "/api/v1/expected-concepts/bulk",
        json=[
            _payload(rubric_criterion_id=str(criterion.id), concept_name="Concept one"),
            _payload(rubric_criterion_id=str(criterion.id), concept_name="Concept two"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert body["errors"] == []


async def test_bulk_create_expected_concepts_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ecbulk2", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="BULKERR")
    token = await _login(client, "ecbulk2")
    headers = _institution_headers(token, criterion.institution_id)

    response = await client.post(
        "/api/v1/expected-concepts/bulk",
        json=[
            _payload(rubric_criterion_id=str(criterion.id), concept_name="Valid concept"),
            _payload(rubric_criterion_id=str(uuid.uuid4()), concept_name="Orphan concept"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["index"] == 1
    assert "message" in body["errors"][0]


async def test_export_expected_concepts_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ecexport1", role=seed_rbac["super_admin"])
    token = await _login(client, "ecexport1")

    response = await client.get("/api/v1/expected-concepts/export", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_expected_concepts_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ecimport1", role=seed_rbac["super_admin"])
    token = await _login(client, "ecimport1")

    response = await client.post("/api/v1/expected-concepts/import", headers=auth_headers(token))

    assert response.status_code == 202
    assert response.json()["status"] == "not_implemented"


async def test_update_expected_concept_accepts_new_rubric_criterion_in_same_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ecadmin11", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="UPDFK")
    other_criterion = await _create_second_criterion(db_session, criterion, code="UPDFK2")
    token = await _login(client, "ecadmin11")
    headers = _institution_headers(token, criterion.institution_id)

    created = await client.post(
        "/api/v1/expected-concepts",
        json=_payload(rubric_criterion_id=str(criterion.id)),
        headers=headers,
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/expected-concepts/{entity_id}",
        json={"rubric_criterion_id": str(other_criterion.id)},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["rubric_criterion_id"] == str(other_criterion.id)


async def test_update_expected_concept_rejects_nonexistent_rubric_criterion(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ecadmin12", role=seed_rbac["super_admin"])
    criterion = await _create_criterion(db_session, code="UPDBAD")
    token = await _login(client, "ecadmin12")
    headers = _institution_headers(token, criterion.institution_id)

    created = await client.post(
        "/api/v1/expected-concepts",
        json=_payload(rubric_criterion_id=str(criterion.id)),
        headers=headers,
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/expected-concepts/{entity_id}",
        json={"rubric_criterion_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404
