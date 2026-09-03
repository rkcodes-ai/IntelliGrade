"""AnswerKey management API tests: CRUD, tenancy, 1:1 uniqueness, versioning.

`Question` and its full Module 03/04 parent chain are sibling entities built
in earlier waves — `_create_question` builds them directly via the ORM
(mirroring `test_questions_api.py`'s `_create_subject`/`_create_lookup_rows`
helpers) since they are parent-chain scaffolding here, not the entity under
test.
"""

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


class _QuestionContext:
    """A persisted parent chain (institution + lookups) multiple `Question`
    rows can be created against, so tests can build several sibling
    questions (and thus several answer keys) within one institution."""

    def __init__(self, institution: Institution, subject: Subject, lookups: dict[str, uuid.UUID]):
        self.institution = institution
        self.subject = subject
        self.lookups = lookups


async def _create_question_context(db_session: AsyncSession, *, code: str) -> _QuestionContext:
    """Builds the full Module 03/04 parent chain a `Question` needs."""
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
    await db_session.commit()
    await db_session.refresh(subject)

    return _QuestionContext(
        institution,
        subject,
        {
            "question_category_id": category.id,
            "question_type_id": question_type.id,
            "difficulty_level_id": difficulty.id,
            "bloom_level_id": bloom.id,
        },
    )


async def _add_question(db_session: AsyncSession, ctx: _QuestionContext, *, code: str) -> Question:
    """Adds one more `Question` row within an existing `_QuestionContext`."""
    question = Question(
        institution_id=ctx.institution.id,
        subject_id=ctx.subject.id,
        question_category_id=ctx.lookups["question_category_id"],
        question_type_id=ctx.lookups["question_type_id"],
        difficulty_level_id=ctx.lookups["difficulty_level_id"],
        bloom_level_id=ctx.lookups["bloom_level_id"],
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


async def _create_question(db_session: AsyncSession, *, code: str) -> Question:
    """Builds the full parent chain and returns a single persisted `Question`."""
    ctx = await _create_question_context(db_session, code=code)
    return await _add_question(db_session, ctx, code=code)


def _payload(question_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "question_id": str(question_id),
        "reference_answer": "The mitochondria is the powerhouse of the cell.",
    }
    payload.update(overrides)
    return payload


async def test_create_answer_key_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="akadmin1", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="CREATE")
    token = await _login(client, "akadmin1")

    response = await client.post(
        "/api/v1/answer-keys",
        json=_payload(question.id),
        headers=_institution_headers(token, question.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["question_id"] == str(question.id)
    assert body["reference_answer"] == "The mitochondria is the powerhouse of the cell."
    assert body["current_version"] == 1
    assert body["expected_length"] is None
    assert body["confidence_threshold"] is None


async def test_create_answer_key_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="akadmin2", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="NOHEADER")
    token = await _login(client, "akadmin2")

    response = await client.post(
        "/api/v1/answer-keys", json=_payload(question.id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_answer_key_rejects_nonexistent_question(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="akadmin3", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="BADQUESTION")
    token = await _login(client, "akadmin3")

    response = await client.post(
        "/api/v1/answer-keys",
        json=_payload(uuid.uuid4()),
        headers=_institution_headers(token, question.institution_id),
    )

    assert response.status_code == 404


async def test_create_answer_key_rejects_duplicate_for_same_question(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="akadmin4", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="DUP")
    token = await _login(client, "akadmin4")
    headers = _institution_headers(token, question.institution_id)

    first = await client.post("/api/v1/answer-keys", json=_payload(question.id), headers=headers)
    assert first.status_code == 201

    second = await client.post("/api/v1/answer-keys", json=_payload(question.id), headers=headers)
    assert second.status_code == 409


async def test_non_privileged_role_cannot_create_answer_key(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="akstudent1", role=seed_rbac["student"])
    question = await _create_question(db_session, code="FORBIDDEN")
    token = await _login(client, "akstudent1")

    response = await client.post(
        "/api/v1/answer-keys",
        json=_payload(question.id),
        headers=_institution_headers(token, question.institution_id),
    )

    assert response.status_code == 403


async def test_get_nonexistent_answer_key_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="akadmin5", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="GETMISSING")
    token = await _login(client, "akadmin5")

    response = await client.get(
        f"/api/v1/answer-keys/{uuid.uuid4()}",
        headers=_institution_headers(token, question.institution_id),
    )

    assert response.status_code == 404


async def test_answer_key_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="akadmin6", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="ROUNDTRIP")
    token = await _login(client, "akadmin6")
    headers = _institution_headers(token, question.institution_id)

    created = await client.post("/api/v1/answer-keys", json=_payload(question.id), headers=headers)
    assert created.status_code == 201
    entity_id = created.json()["id"]
    created_updated_at = created.json()["updated_at"]

    get_response = await client.get(f"/api/v1/answer-keys/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert (
        get_response.json()["reference_answer"] == "The mitochondria is the powerhouse of the cell."
    )

    update_response = await client.patch(
        f"/api/v1/answer-keys/{entity_id}",
        json={"evaluation_notes": "Accept partial credit for structure alone."},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert (
        update_response.json()["evaluation_notes"] == "Accept partial credit for structure alone."
    )
    # SQLite's func.now() is whole-second resolution -- use >=, not !=.
    assert update_response.json()["updated_at"] >= created_updated_at

    delete_response = await client.delete(f"/api/v1/answer-keys/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/answer-keys/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/answer-keys/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/answer-keys/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/answer-keys/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_update_answer_key_increments_version_on_reference_answer_change(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="akadmin7", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="VERSION")
    token = await _login(client, "akadmin7")
    headers = _institution_headers(token, question.institution_id)

    created = await client.post("/api/v1/answer-keys", json=_payload(question.id), headers=headers)
    assert created.status_code == 201
    entity_id = created.json()["id"]
    assert created.json()["current_version"] == 1

    # A cosmetic field change alone must NOT bump the version counter.
    cosmetic_update = await client.patch(
        f"/api/v1/answer-keys/{entity_id}",
        json={"evaluation_notes": "Cosmetic only"},
        headers=headers,
    )
    assert cosmetic_update.status_code == 200
    assert cosmetic_update.json()["current_version"] == 1

    # Changing `reference_answer` (graded content) must bump it.
    content_update = await client.patch(
        f"/api/v1/answer-keys/{entity_id}",
        json={"reference_answer": "Updated reference answer."},
        headers=headers,
    )
    assert content_update.status_code == 200
    assert content_update.json()["current_version"] == 2
    assert content_update.json()["reference_answer"] == "Updated reference answer."


async def test_list_answer_keys_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="akadmin8", role=seed_rbac["super_admin"])
    token = await _login(client, "akadmin8")
    ctx = await _create_question_context(db_session, code="LIST")
    headers = _institution_headers(token, ctx.institution.id)

    for i in range(5):
        question = await _add_question(db_session, ctx, code=f"LIST{i}")
        response = await client.post(
            "/api/v1/answer-keys",
            json=_payload(question.id, reference_answer=f"Answer {i}"),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/answer-keys?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_answer_keys_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="akbulk1", role=seed_rbac["super_admin"])
    ctx = await _create_question_context(db_session, code="BULK")
    question1 = await _add_question(db_session, ctx, code="BULK1")
    question2 = await _add_question(db_session, ctx, code="BULK2")
    token = await _login(client, "akbulk1")
    headers = _institution_headers(token, ctx.institution.id)

    response = await client.post(
        "/api/v1/answer-keys/bulk",
        json=[
            _payload(question1.id, reference_answer="First answer"),
            _payload(question2.id, reference_answer="Second answer"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert body["errors"] == []


async def test_bulk_create_answer_keys_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="akbulk2", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="BULKERR")
    token = await _login(client, "akbulk2")
    headers = _institution_headers(token, question.institution_id)
    bad_question_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/answer-keys/bulk",
        json=[
            _payload(question.id, reference_answer="Valid answer"),
            _payload(bad_question_id, reference_answer="Orphan answer"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["index"] == 1
    assert body["errors"][0]["question_id"] == str(bad_question_id)


async def test_export_answer_keys_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="akexport1", role=seed_rbac["super_admin"])
    token = await _login(client, "akexport1")

    response = await client.get("/api/v1/answer-keys/export", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_answer_keys_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="akimport1", role=seed_rbac["super_admin"])
    token = await _login(client, "akimport1")

    response = await client.post("/api/v1/answer-keys/import", headers=auth_headers(token))

    assert response.status_code == 202
    assert response.json()["status"] == "not_implemented"
