"""QuestionReview API tests: CRUD, tenancy, soft-delete/restore, bulk-create, rating validation."""

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


async def _create_subject(db_session: AsyncSession, *, code: str) -> Subject:
    """Builds the full Module 03 parent chain a `Question` needs and returns the `Subject`."""
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


async def _create_lookup_rows(
    db_session: AsyncSession, institution_id: uuid.UUID, *, code: str
) -> dict[str, uuid.UUID]:
    category = QuestionCategory(
        institution_id=institution_id, code=f"QC-{code}", name=f"Category {code}"
    )
    question_type = QuestionType(
        institution_id=institution_id, code=f"QT-{code}", name=f"Type {code}"
    )
    difficulty = DifficultyLevel(
        institution_id=institution_id, code=f"DL-{code}", name=f"Difficulty {code}", level_order=1
    )
    bloom = BloomTaxonomyLevel(
        institution_id=institution_id, code=f"BL-{code}", name=f"Bloom {code}", level_order=1
    )
    db_session.add_all([category, question_type, difficulty, bloom])
    await db_session.flush()
    await db_session.commit()
    for row in (category, question_type, difficulty, bloom):
        await db_session.refresh(row)
    return {
        "question_category_id": category.id,
        "question_type_id": question_type.id,
        "difficulty_level_id": difficulty.id,
        "bloom_level_id": bloom.id,
    }


def _question_payload(
    subject_id: uuid.UUID, lookups: dict[str, uuid.UUID], **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "subject_id": str(subject_id),
        "question_category_id": str(lookups["question_category_id"]),
        "question_type_id": str(lookups["question_type_id"]),
        "difficulty_level_id": str(lookups["difficulty_level_id"]),
        "bloom_level_id": str(lookups["bloom_level_id"]),
        "question_text": "What is 2 + 2?",
        "marks": 5.0,
    }
    payload.update(overrides)
    return payload


async def _setup(db_session: AsyncSession, *, code: str) -> tuple[Subject, dict[str, uuid.UUID]]:
    subject = await _create_subject(db_session, code=code)
    lookups = await _create_lookup_rows(db_session, subject.institution_id, code=code)
    return subject, lookups


async def _create_question(
    client: AsyncClient, headers: dict[str, str], subject: Subject, lookups: dict[str, uuid.UUID]
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/questions", json=_question_payload(subject.id, lookups), headers=headers
    )
    assert response.status_code == 201
    body: dict[str, object] = response.json()
    return body


def _review_payload(question_id: object, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "question_id": str(question_id),
        "comment": "Clear and well-scoped question.",
        "rating": 4,
    }
    payload.update(overrides)
    return payload


async def test_create_question_review_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    admin = await create_test_user(db_session, username="qradmin1", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="REV1")
    token = await _login(client, "qradmin1")
    headers = _institution_headers(token, subject.institution_id)

    question = await _create_question(client, headers, subject, lookups)

    response = await client.post(
        "/api/v1/question-reviews", json=_review_payload(question["id"]), headers=headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["question_id"] == question["id"]
    assert body["comment"] == "Clear and well-scoped question."
    assert body["rating"] == 4
    # reviewer_id is never client-supplied -- it comes from the authenticated caller.
    assert body["reviewer_id"] == str(admin.id)


async def test_create_question_review_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qradmin2", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="REV2")
    token = await _login(client, "qradmin2")
    headers = _institution_headers(token, subject.institution_id)

    question = await _create_question(client, headers, subject, lookups)

    response = await client.post(
        "/api/v1/question-reviews",
        json=_review_payload(question["id"]),
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_question_review_rejects_nonexistent_question(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qradmin3", role=seed_rbac["super_admin"])
    subject, _lookups = await _setup(db_session, code="REV3")
    token = await _login(client, "qradmin3")
    headers = _institution_headers(token, subject.institution_id)

    response = await client.post(
        "/api/v1/question-reviews", json=_review_payload(uuid.uuid4()), headers=headers
    )

    assert response.status_code == 404


async def test_create_question_review_rejects_rating_out_of_range(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qradmin4", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="REV4")
    token = await _login(client, "qradmin4")
    headers = _institution_headers(token, subject.institution_id)

    question = await _create_question(client, headers, subject, lookups)

    response = await client.post(
        "/api/v1/question-reviews",
        json=_review_payload(question["id"], rating=6),
        headers=headers,
    )

    assert response.status_code == 422


async def test_non_privileged_role_cannot_create_question_review(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qrstudent1", role=seed_rbac["student"])
    await create_test_user(db_session, username="qradmin5", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="REV5")
    admin_token = await _login(client, "qradmin5")
    admin_headers = _institution_headers(admin_token, subject.institution_id)

    question = await _create_question(client, admin_headers, subject, lookups)

    student_token = await _login(client, "qrstudent1")
    response = await client.post(
        "/api/v1/question-reviews",
        json=_review_payload(question["id"]),
        headers=_institution_headers(student_token, subject.institution_id),
    )

    assert response.status_code == 403


async def test_get_nonexistent_question_review_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qradmin6", role=seed_rbac["super_admin"])
    subject, _lookups = await _setup(db_session, code="REV6")
    token = await _login(client, "qradmin6")
    headers = _institution_headers(token, subject.institution_id)

    response = await client.get(f"/api/v1/question-reviews/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404


async def test_question_review_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qradmin7", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="REV7")
    token = await _login(client, "qradmin7")
    headers = _institution_headers(token, subject.institution_id)

    question = await _create_question(client, headers, subject, lookups)
    created = await client.post(
        "/api/v1/question-reviews", json=_review_payload(question["id"]), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    created_updated_at = created.json()["updated_at"]

    get_response = await client.get(f"/api/v1/question-reviews/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["comment"] == "Clear and well-scoped question."

    update_response = await client.patch(
        f"/api/v1/question-reviews/{entity_id}",
        json={"comment": "Updated comment.", "rating": 5},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["comment"] == "Updated comment."
    assert update_response.json()["rating"] == 5
    # SQLite's func.now() is whole-second resolution -- use >=, not !=.
    assert update_response.json()["updated_at"] >= created_updated_at

    delete_response = await client.delete(f"/api/v1/question-reviews/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/question-reviews/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/question-reviews/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/question-reviews/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/question-reviews/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_list_question_reviews_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qradmin8", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="REV8")
    token = await _login(client, "qradmin8")
    headers = _institution_headers(token, subject.institution_id)

    question = await _create_question(client, headers, subject, lookups)
    for i in range(5):
        response = await client.post(
            "/api/v1/question-reviews",
            json=_review_payload(question["id"], comment=f"Review {i}"),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/question-reviews?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_question_reviews_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qradmin9", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="REV9")
    token = await _login(client, "qradmin9")
    headers = _institution_headers(token, subject.institution_id)

    question = await _create_question(client, headers, subject, lookups)

    response = await client.post(
        "/api/v1/question-reviews/bulk",
        json=[
            _review_payload(question["id"], comment="Bulk one"),
            _review_payload(uuid.uuid4(), comment="Bulk missing question"),
            _review_payload(question["id"], comment="Bulk two"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


async def test_export_question_reviews_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qradmin10", role=seed_rbac["super_admin"])
    subject, _lookups = await _setup(db_session, code="EXPORT")
    token = await _login(client, "qradmin10")
    headers = _institution_headers(token, subject.institution_id)

    response = await client.get("/api/v1/question-reviews/export", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_question_reviews_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qradmin11", role=seed_rbac["super_admin"])
    subject, _lookups = await _setup(db_session, code="IMPORT")
    token = await _login(client, "qradmin11")
    headers = _institution_headers(token, subject.institution_id)

    response = await client.post("/api/v1/question-reviews/import", headers=headers)

    assert response.status_code == 202
    assert response.json()["status"] == "not_implemented"
