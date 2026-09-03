"""Question management API tests: CRUD, tenancy, versioning, approval workflow, tag mapping.

NOTE: `QuestionCategory`, `QuestionType`, `DifficultyLevel`, `BloomTaxonomyLevel`,
and `QuestionTag` are sibling Module 04 lookup tables built by other agents in
the same implementation wave — their real schema isn't visible from this file.
`_create_lookup_rows` below assumes they follow this codebase's universal
lookup-entity shape (`institution_id`, `code`, `name`, `is_active` — see
`app/models/subject_category.py`), matching how `test_class_schedules_api.py`
and `test_subjects_api.py` build their own sibling-entity parent chains
directly via the ORM. Verify/adjust this helper at the central integration
step if the real column names differ.
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
from app.models.question_category import QuestionCategory
from app.models.question_tag import QuestionTag
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
    """Seeds one row in each Module 04 lookup table `Question` FKs into."""
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
    tag = QuestionTag(institution_id=institution_id, name=f"Tag {code}")
    db_session.add_all([category, question_type, difficulty, bloom, tag])
    await db_session.flush()
    await db_session.commit()
    for row in (category, question_type, difficulty, bloom, tag):
        await db_session.refresh(row)
    return {
        "question_category_id": category.id,
        "question_type_id": question_type.id,
        "difficulty_level_id": difficulty.id,
        "bloom_level_id": bloom.id,
        "tag_id": tag.id,
    }


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


def _payload(
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


async def test_create_question_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin1", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="CREATE")
    token = await _login(client, "qadmin1")

    response = await client.post(
        "/api/v1/questions",
        json=_payload(subject.id, lookups),
        headers=_institution_headers(token, subject.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["subject_id"] == str(subject.id)
    assert body["question_text"] == "What is 2 + 2?"
    assert float(body["marks"]) == 5.0
    assert body["language"] == "en"
    assert body["is_active"] is True
    assert body["current_version"] == 1
    assert body["approval_status"] == "draft"
    assert body["approved_by"] is None
    assert body["approved_at"] is None


async def test_create_question_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin2", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="NOHEADER")
    token = await _login(client, "qadmin2")

    response = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_question_rejects_nonexistent_subject(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin3", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="BADSUBJECT")
    token = await _login(client, "qadmin3")

    response = await client.post(
        "/api/v1/questions",
        json=_payload(uuid.uuid4(), lookups),
        headers=_institution_headers(token, subject.institution_id),
    )

    assert response.status_code == 404


async def test_create_question_rejects_nonexistent_category(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin4", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="BADCATEGORY")
    token = await _login(client, "qadmin4")

    response = await client.post(
        "/api/v1/questions",
        json=_payload(subject.id, lookups, question_category_id=str(uuid.uuid4())),
        headers=_institution_headers(token, subject.institution_id),
    )

    assert response.status_code == 404


async def test_create_question_rejects_nonexistent_question_type(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin5", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="BADTYPE")
    token = await _login(client, "qadmin5")

    response = await client.post(
        "/api/v1/questions",
        json=_payload(subject.id, lookups, question_type_id=str(uuid.uuid4())),
        headers=_institution_headers(token, subject.institution_id),
    )

    assert response.status_code == 404


async def test_create_question_rejects_nonexistent_difficulty_level(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin6", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="BADDIFFICULTY")
    token = await _login(client, "qadmin6")

    response = await client.post(
        "/api/v1/questions",
        json=_payload(subject.id, lookups, difficulty_level_id=str(uuid.uuid4())),
        headers=_institution_headers(token, subject.institution_id),
    )

    assert response.status_code == 404


async def test_create_question_rejects_nonexistent_bloom_level(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin7", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="BADBLOOM")
    token = await _login(client, "qadmin7")

    response = await client.post(
        "/api/v1/questions",
        json=_payload(subject.id, lookups, bloom_level_id=str(uuid.uuid4())),
        headers=_institution_headers(token, subject.institution_id),
    )

    assert response.status_code == 404


async def test_non_privileged_role_cannot_create_question(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qstudent1", role=seed_rbac["student"])
    subject, lookups = await _setup(db_session, code="FORBIDDEN")
    token = await _login(client, "qstudent1")

    response = await client.post(
        "/api/v1/questions",
        json=_payload(subject.id, lookups),
        headers=_institution_headers(token, subject.institution_id),
    )

    assert response.status_code == 403


async def test_get_nonexistent_question_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin8", role=seed_rbac["super_admin"])
    subject, _lookups = await _setup(db_session, code="GETMISSING")
    token = await _login(client, "qadmin8")

    response = await client.get(
        f"/api/v1/questions/{uuid.uuid4()}",
        headers=_institution_headers(token, subject.institution_id),
    )

    assert response.status_code == 404


async def test_question_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin9", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="ROUNDTRIP")
    token = await _login(client, "qadmin9")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    created_updated_at = created.json()["updated_at"]

    get_response = await client.get(f"/api/v1/questions/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["question_text"] == "What is 2 + 2?"

    update_response = await client.patch(
        f"/api/v1/questions/{entity_id}", json={"topic": "Arithmetic"}, headers=headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["topic"] == "Arithmetic"
    # SQLite's func.now() is whole-second resolution -- use >=, not !=.
    assert update_response.json()["updated_at"] >= created_updated_at

    delete_response = await client.delete(f"/api/v1/questions/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/questions/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/questions/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(f"/api/v1/questions/{entity_id}/restore", headers=headers)
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/questions/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_list_questions_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin10", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="LIST")
    token = await _login(client, "qadmin10")
    headers = _institution_headers(token, subject.institution_id)

    for i in range(5):
        response = await client.post(
            "/api/v1/questions",
            json=_payload(subject.id, lookups, question_text=f"Question {i}?"),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/questions?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_update_question_increments_version_on_marks_or_text_change(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin11", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="VERSION")
    token = await _login(client, "qadmin11")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    assert created.json()["current_version"] == 1

    # A cosmetic field change alone must NOT bump the version counter.
    cosmetic_update = await client.patch(
        f"/api/v1/questions/{entity_id}", json={"topic": "Cosmetic only"}, headers=headers
    )
    assert cosmetic_update.status_code == 200
    assert cosmetic_update.json()["current_version"] == 1

    # Changing `marks` (graded content) must bump it.
    marks_update = await client.patch(
        f"/api/v1/questions/{entity_id}", json={"marks": 10.0}, headers=headers
    )
    assert marks_update.status_code == 200
    assert marks_update.json()["current_version"] == 2
    assert float(marks_update.json()["marks"]) == 10.0


async def test_submit_for_review_then_approve_flow(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    admin = await create_test_user(db_session, username="qadmin12", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="APPROVE")
    token = await _login(client, "qadmin12")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=headers
    )
    entity_id = created.json()["id"]

    # Approving a draft (not yet submitted) must 409.
    premature_approve = await client.post(f"/api/v1/questions/{entity_id}/approve", headers=headers)
    assert premature_approve.status_code == 409

    submit_response = await client.post(
        f"/api/v1/questions/{entity_id}/submit-for-review", headers=headers
    )
    assert submit_response.status_code == 200
    assert submit_response.json()["approval_status"] == "pending_review"

    approve_response = await client.post(f"/api/v1/questions/{entity_id}/approve", headers=headers)
    assert approve_response.status_code == 200
    body = approve_response.json()
    assert body["approval_status"] == "approved"
    assert body["approved_by"] == str(admin.id)
    assert body["approved_at"] is not None

    # Approving again (now "approved", not "pending_review") must 409.
    second_approve = await client.post(f"/api/v1/questions/{entity_id}/approve", headers=headers)
    assert second_approve.status_code == 409


async def test_submit_for_review_then_reject_flow(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin13", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="REJECT")
    token = await _login(client, "qadmin13")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=headers
    )
    entity_id = created.json()["id"]

    # Rejecting a draft (not yet submitted) must 409.
    premature_reject = await client.post(
        f"/api/v1/questions/{entity_id}/reject", json={"reason": "too early"}, headers=headers
    )
    assert premature_reject.status_code == 409

    submit_response = await client.post(
        f"/api/v1/questions/{entity_id}/submit-for-review", headers=headers
    )
    assert submit_response.status_code == 200

    reject_response = await client.post(
        f"/api/v1/questions/{entity_id}/reject",
        json={"reason": "Question text is ambiguous."},
        headers=headers,
    )
    assert reject_response.status_code == 200
    body = reject_response.json()
    assert body["approval_status"] == "rejected"
    assert body["rejection_reason"] == "Question text is ambiguous."

    # A rejected question may be resubmitted for review.
    resubmit_response = await client.post(
        f"/api/v1/questions/{entity_id}/submit-for-review", headers=headers
    )
    assert resubmit_response.status_code == 200
    assert resubmit_response.json()["approval_status"] == "pending_review"

    # Rejecting again (now "pending_review" again, fine) then rejecting the
    # *already-rejected* result a second time in a row must 409.
    reject_again = await client.post(
        f"/api/v1/questions/{entity_id}/reject", json={"reason": "still ambiguous"}, headers=headers
    )
    assert reject_again.status_code == 200

    reject_third_time = await client.post(
        f"/api/v1/questions/{entity_id}/reject", json={"reason": "once more"}, headers=headers
    )
    assert reject_third_time.status_code == 409


async def test_question_tag_add_and_remove_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin14", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="TAGS")
    token = await _login(client, "qadmin14")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=headers
    )
    entity_id = created.json()["id"]
    tag_id = str(lookups["tag_id"])

    add_response = await client.post(
        f"/api/v1/questions/{entity_id}/tags", json={"tag_id": tag_id}, headers=headers
    )
    assert add_response.status_code == 201
    assert add_response.json()["tag_id"] == tag_id
    assert add_response.json()["question_id"] == entity_id

    duplicate_add = await client.post(
        f"/api/v1/questions/{entity_id}/tags", json={"tag_id": tag_id}, headers=headers
    )
    assert duplicate_add.status_code == 409

    remove_response = await client.delete(
        f"/api/v1/questions/{entity_id}/tags/{tag_id}", headers=headers
    )
    assert remove_response.status_code == 204

    remove_again = await client.delete(
        f"/api/v1/questions/{entity_id}/tags/{tag_id}", headers=headers
    )
    assert remove_again.status_code == 404


async def test_bulk_create_questions_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin15", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="BULKOK")
    token = await _login(client, "qadmin15")
    headers = _institution_headers(token, subject.institution_id)

    response = await client.post(
        "/api/v1/questions/bulk",
        json=[
            _payload(subject.id, lookups, question_text="Bulk question one?"),
            _payload(subject.id, lookups, question_text="Bulk question two?"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert body["errors"] == []


async def test_bulk_create_questions_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin16", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="BULKERR")
    token = await _login(client, "qadmin16")
    headers = _institution_headers(token, subject.institution_id)

    response = await client.post(
        "/api/v1/questions/bulk",
        json=[
            _payload(subject.id, lookups, question_text="Valid question?"),
            _payload(uuid.uuid4(), lookups, question_text="Missing subject question?"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1


async def test_export_questions_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin17", role=seed_rbac["super_admin"])
    subject, _lookups = await _setup(db_session, code="EXPORT")
    token = await _login(client, "qadmin17")
    headers = _institution_headers(token, subject.institution_id)

    response = await client.get("/api/v1/questions/export", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_questions_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin18", role=seed_rbac["super_admin"])
    subject, _lookups = await _setup(db_session, code="IMPORT")
    token = await _login(client, "qadmin18")
    headers = _institution_headers(token, subject.institution_id)

    response = await client.post("/api/v1/questions/import", headers=headers)

    assert response.status_code == 202
    assert response.json()["status"] == "not_implemented"


async def test_update_question_accepts_new_subject_in_same_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin19", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="UPDSUBJ")
    other_subject = await _create_second_subject(db_session, subject, code="UPDSUBJ2")
    token = await _login(client, "qadmin19")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/questions/{entity_id}",
        json={"subject_id": str(other_subject.id)},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["subject_id"] == str(other_subject.id)


async def test_update_question_rejects_nonexistent_subject(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin20", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="UPDBADSUBJ")
    token = await _login(client, "qadmin20")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/questions/{entity_id}",
        json={"subject_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404


async def test_update_question_accepts_new_question_category(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin21", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="UPDCAT")
    other_lookups = await _create_lookup_rows(db_session, subject.institution_id, code="UPDCAT2")
    token = await _login(client, "qadmin21")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/questions/{entity_id}",
        json={"question_category_id": str(other_lookups["question_category_id"])},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["question_category_id"] == str(
        other_lookups["question_category_id"]
    )


async def test_update_question_rejects_nonexistent_question_category(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin22", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="UPDBADCAT")
    token = await _login(client, "qadmin22")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/questions/{entity_id}",
        json={"question_category_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404


async def test_update_question_accepts_new_question_type(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin23", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="UPDTYPE")
    other_lookups = await _create_lookup_rows(db_session, subject.institution_id, code="UPDTYPE2")
    token = await _login(client, "qadmin23")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/questions/{entity_id}",
        json={"question_type_id": str(other_lookups["question_type_id"])},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["question_type_id"] == str(other_lookups["question_type_id"])


async def test_update_question_rejects_nonexistent_question_type(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin24", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="UPDBADTYPE")
    token = await _login(client, "qadmin24")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/questions/{entity_id}",
        json={"question_type_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404


async def test_update_question_accepts_new_difficulty_level(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin25", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="UPDDIFF")
    other_lookups = await _create_lookup_rows(db_session, subject.institution_id, code="UPDDIFF2")
    token = await _login(client, "qadmin25")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/questions/{entity_id}",
        json={"difficulty_level_id": str(other_lookups["difficulty_level_id"])},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["difficulty_level_id"] == str(
        other_lookups["difficulty_level_id"]
    )


async def test_update_question_rejects_nonexistent_difficulty_level(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin26", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="UPDBADDIFF")
    token = await _login(client, "qadmin26")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/questions/{entity_id}",
        json={"difficulty_level_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404


async def test_update_question_accepts_new_bloom_level(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin27", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="UPDBLOOM")
    other_lookups = await _create_lookup_rows(db_session, subject.institution_id, code="UPDBLOOM2")
    token = await _login(client, "qadmin27")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/questions/{entity_id}",
        json={"bloom_level_id": str(other_lookups["bloom_level_id"])},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["bloom_level_id"] == str(other_lookups["bloom_level_id"])


async def test_update_question_rejects_nonexistent_bloom_level(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin28", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="UPDBADBLOOM")
    token = await _login(client, "qadmin28")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/questions/{entity_id}",
        json={"bloom_level_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404


async def test_submit_for_review_rejects_when_already_pending(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin29", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="RESUBMIT")
    token = await _login(client, "qadmin29")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=headers
    )
    entity_id = created.json()["id"]

    first_submit = await client.post(
        f"/api/v1/questions/{entity_id}/submit-for-review", headers=headers
    )
    assert first_submit.status_code == 200

    second_submit = await client.post(
        f"/api/v1/questions/{entity_id}/submit-for-review", headers=headers
    )
    assert second_submit.status_code == 409


async def test_add_tag_rejects_nonexistent_tag(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qadmin30", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="BADTAG")
    token = await _login(client, "qadmin30")
    headers = _institution_headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/questions", json=_payload(subject.id, lookups), headers=headers
    )
    entity_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/questions/{entity_id}/tags",
        json={"tag_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert response.status_code == 404
