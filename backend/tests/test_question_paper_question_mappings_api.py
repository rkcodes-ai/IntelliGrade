"""QuestionPaperQuestionMapping API tests: CRUD, tenancy, unique-pair rejection.

`QuestionPaper` is a sibling Module 04 model built by another agent in the
same implementation wave; `_create_section` builds its Assessment->
QuestionPaper->QuestionPaperSection chain directly via the ORM (reusing an
already-persisted subject from `_create_question`), mirroring
`test_assessment_configurations_api.py`'s `_create_assessment` helper.
`QuestionPaperSection` and `Question` are both real (the former written by
this same agent, the latter already merged from Wave 1), so their helpers
use the exact required columns.
"""

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.assessment_status import AssessmentStatus
from app.models.assessment_type import AssessmentType
from app.models.bloom_taxonomy_level import BloomTaxonomyLevel
from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.difficulty_level import DifficultyLevel
from app.models.institution import Institution
from app.models.program import Program
from app.models.question import Question
from app.models.question_category import QuestionCategory
from app.models.question_paper import QuestionPaper
from app.models.question_paper_section import QuestionPaperSection
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
    """Builds the full Institution->...->Subject->lookup-rows->Question parent chain."""
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
        question_text=f"Question text {code}",
        marks=Decimal("5.00"),
    )
    db_session.add(question)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(question)
    return question


async def _create_section(
    db_session: AsyncSession, institution_id: uuid.UUID, subject_id: uuid.UUID, *, code: str
) -> QuestionPaperSection:
    """
    Builds the Assessment->QuestionPaper->QuestionPaperSection chain,
    reusing an already-persisted `subject_id` (from `_create_question`)
    rather than building a second Subject under the same institution.
    """
    assessment_type = AssessmentType(
        institution_id=institution_id, code=f"AT-{code}", name=f"Type {code}"
    )
    db_session.add(assessment_type)
    await db_session.flush()

    assessment_status = AssessmentStatus(
        institution_id=institution_id, code=f"AS-{code}", name=f"Status {code}"
    )
    db_session.add(assessment_status)
    await db_session.flush()

    assessment = Assessment(
        institution_id=institution_id,
        subject_id=subject_id,
        assessment_type_id=assessment_type.id,
        assessment_status_id=assessment_status.id,
        name=f"Assessment {code}",
    )
    db_session.add(assessment)
    await db_session.flush()

    paper = QuestionPaper(
        institution_id=institution_id,
        assessment_id=assessment.id,
        name=f"Paper {code}",
        total_marks=Decimal("100.00"),
    )
    db_session.add(paper)
    await db_session.flush()

    section = QuestionPaperSection(
        institution_id=institution_id, question_paper_id=paper.id, name=f"Section {code}"
    )
    db_session.add(section)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(section)
    return section


async def _create_second_question(
    db_session: AsyncSession, question: Question, *, code: str
) -> Question:
    """A second `Question` in the same institution, reusing `question`'s
    subject/lookup FKs, so update tests can PATCH `question_id` to a
    different-but-still-valid question within the same tenant."""
    second = Question(
        institution_id=question.institution_id,
        subject_id=question.subject_id,
        question_category_id=question.question_category_id,
        question_type_id=question.question_type_id,
        difficulty_level_id=question.difficulty_level_id,
        bloom_level_id=question.bloom_level_id,
        question_text=f"Question text {code}",
        marks=Decimal("5.00"),
    )
    db_session.add(second)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(second)
    return second


def _payload(
    question_paper_section_id: uuid.UUID, question_id: uuid.UUID, **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "question_paper_section_id": str(question_paper_section_id),
        "question_id": str(question_id),
        "order_index": 0,
        "marks_override": "3.00",
        "is_optional": False,
    }
    payload.update(overrides)
    return payload


async def test_create_question_paper_question_mapping_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmadmin1", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="CREATE")
    section = await _create_section(
        db_session, question.institution_id, question.subject_id, code="CREATE"
    )
    token = await _login(client, "qpqmadmin1")

    response = await client.post(
        "/api/v1/question-paper-question-mappings",
        json=_payload(section.id, question.id),
        headers=_institution_headers(token, question.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["question_paper_section_id"] == str(section.id)
    assert body["question_id"] == str(question.id)
    assert body["marks_override"] == "3.00"
    assert body["is_optional"] is False


async def test_create_question_paper_question_mapping_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmadmin2", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="NOHEADER")
    section = await _create_section(
        db_session, question.institution_id, question.subject_id, code="NOHEADER"
    )
    token = await _login(client, "qpqmadmin2")

    response = await client.post(
        "/api/v1/question-paper-question-mappings",
        json=_payload(section.id, question.id),
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_question_paper_question_mapping_rejects_nonexistent_section(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmadmin3", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="BADSECTION")
    token = await _login(client, "qpqmadmin3")

    response = await client.post(
        "/api/v1/question-paper-question-mappings",
        json=_payload(uuid.uuid4(), question.id),
        headers=_institution_headers(token, question.institution_id),
    )

    assert response.status_code == 404


async def test_create_question_paper_question_mapping_rejects_nonexistent_question(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmadmin4", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="BADQUESTION")
    section = await _create_section(
        db_session, question.institution_id, question.subject_id, code="BADQUESTION"
    )
    token = await _login(client, "qpqmadmin4")

    response = await client.post(
        "/api/v1/question-paper-question-mappings",
        json=_payload(section.id, uuid.uuid4()),
        headers=_institution_headers(token, question.institution_id),
    )

    assert response.status_code == 404


async def test_create_question_paper_question_mapping_rejects_duplicate(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmadmin5", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="DUPE")
    section = await _create_section(
        db_session, question.institution_id, question.subject_id, code="DUPE"
    )
    token = await _login(client, "qpqmadmin5")
    headers = _institution_headers(token, question.institution_id)

    first = await client.post(
        "/api/v1/question-paper-question-mappings",
        json=_payload(section.id, question.id),
        headers=headers,
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/question-paper-question-mappings",
        json=_payload(section.id, question.id),
        headers=headers,
    )
    assert second.status_code == 409


async def test_non_privileged_role_cannot_create_question_paper_question_mapping(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmstudent1", role=seed_rbac["student"])
    question = await _create_question(db_session, code="FORBIDDEN")
    section = await _create_section(
        db_session, question.institution_id, question.subject_id, code="FORBIDDEN"
    )
    token = await _login(client, "qpqmstudent1")

    response = await client.post(
        "/api/v1/question-paper-question-mappings",
        json=_payload(section.id, question.id),
        headers=_institution_headers(token, question.institution_id),
    )

    assert response.status_code == 403


async def test_question_paper_question_mapping_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmadmin6", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="ROUNDTRIP")
    section = await _create_section(
        db_session, question.institution_id, question.subject_id, code="ROUNDTRIP"
    )
    token = await _login(client, "qpqmadmin6")
    headers = _institution_headers(token, question.institution_id)

    create_response = await client.post(
        "/api/v1/question-paper-question-mappings",
        json=_payload(section.id, question.id),
        headers=headers,
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]
    original_updated_at = create_response.json()["updated_at"]

    get_response = await client.get(
        f"/api/v1/question-paper-question-mappings/{entity_id}", headers=headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["order_index"] == 0

    update_response = await client.patch(
        f"/api/v1/question-paper-question-mappings/{entity_id}",
        json={"order_index": 5, "is_optional": True},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert updated_body["order_index"] == 5
    assert updated_body["is_optional"] is True
    # SQLite's func.now() has only whole-second resolution, so a fast
    # create-then-update in the same test can legitimately land in the same
    # second — assert non-decreasing, not strict inequality.
    assert updated_body["updated_at"] >= original_updated_at

    delete_response = await client.delete(
        f"/api/v1/question-paper-question-mappings/{entity_id}", headers=headers
    )
    assert delete_response.status_code == 204

    get_after_delete = await client.get(
        f"/api/v1/question-paper-question-mappings/{entity_id}", headers=headers
    )
    assert get_after_delete.status_code == 404

    deleted_list = await client.get(
        "/api/v1/question-paper-question-mappings/deleted", headers=headers
    )
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/question-paper-question-mappings/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(
        f"/api/v1/question-paper-question-mappings/{entity_id}", headers=headers
    )
    assert get_after_restore.status_code == 200


async def test_question_paper_question_mapping_get_nonexistent_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmadmin7", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="404")
    token = await _login(client, "qpqmadmin7")

    response = await client.get(
        f"/api/v1/question-paper-question-mappings/{uuid.uuid4()}",
        headers=_institution_headers(token, question.institution_id),
    )
    assert response.status_code == 404


async def test_list_question_paper_question_mappings_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmadmin8", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="LIST")
    section = await _create_section(
        db_session, question.institution_id, question.subject_id, code="LIST"
    )
    token = await _login(client, "qpqmadmin8")
    headers = _institution_headers(token, question.institution_id)

    first = await client.post(
        "/api/v1/question-paper-question-mappings",
        json=_payload(section.id, question.id),
        headers=headers,
    )
    assert first.status_code == 201

    for i in range(4):
        # A new Question row under the SAME institution/subject/lookup chain
        # as `question` — a fresh `_create_question` call would build a new
        # Institution each time, which the section (and its institution
        # header) would then not recognize.
        other_question = Question(
            institution_id=question.institution_id,
            subject_id=question.subject_id,
            question_category_id=question.question_category_id,
            question_type_id=question.question_type_id,
            difficulty_level_id=question.difficulty_level_id,
            bloom_level_id=question.bloom_level_id,
            question_text=f"Question text LIST{i}",
            marks=Decimal("5.00"),
        )
        db_session.add(other_question)
        await db_session.flush()
        await db_session.commit()
        await db_session.refresh(other_question)

        response = await client.post(
            "/api/v1/question-paper-question-mappings",
            json=_payload(section.id, other_question.id, order_index=i + 1),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get(
        "/api/v1/question-paper-question-mappings?page=1&page_size=2", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] >= 5


async def test_bulk_create_question_paper_question_mappings_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmadmin9", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="BULKOK")
    section_one = await _create_section(
        db_session, question.institution_id, question.subject_id, code="BULKOK1"
    )
    section_two = await _create_section(
        db_session, question.institution_id, question.subject_id, code="BULKOK2"
    )
    token = await _login(client, "qpqmadmin9")
    headers = _institution_headers(token, question.institution_id)

    response = await client.post(
        "/api/v1/question-paper-question-mappings/bulk",
        json=[
            _payload(section_one.id, question.id),
            _payload(section_two.id, question.id),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert body["errors"] == []


async def test_bulk_create_question_paper_question_mappings_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmadmin10", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="BULKERR")
    section = await _create_section(
        db_session, question.institution_id, question.subject_id, code="BULKERR"
    )
    token = await _login(client, "qpqmadmin10")
    headers = _institution_headers(token, question.institution_id)
    bad_question_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/question-paper-question-mappings/bulk",
        json=[
            _payload(section.id, question.id),
            _payload(section.id, bad_question_id),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["question_id"] == str(bad_question_id)


async def test_export_question_paper_question_mappings_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmadmin11", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="EXPORT")
    token = await _login(client, "qpqmadmin11")
    headers = _institution_headers(token, question.institution_id)

    response = await client.get("/api/v1/question-paper-question-mappings/export", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_question_paper_question_mappings_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmadmin12", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="IMPORT")
    token = await _login(client, "qpqmadmin12")
    headers = _institution_headers(token, question.institution_id)

    response = await client.post("/api/v1/question-paper-question-mappings/import", headers=headers)

    assert response.status_code == 202
    assert response.json()["status"] == "not_implemented"


async def test_update_question_paper_question_mapping_accepts_new_section_in_same_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmadmin13", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="UPDSEC")
    section = await _create_section(
        db_session, question.institution_id, question.subject_id, code="UPDSEC1"
    )
    other_section = await _create_section(
        db_session, question.institution_id, question.subject_id, code="UPDSEC2"
    )
    token = await _login(client, "qpqmadmin13")
    headers = _institution_headers(token, question.institution_id)

    created = await client.post(
        "/api/v1/question-paper-question-mappings",
        json=_payload(section.id, question.id),
        headers=headers,
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-paper-question-mappings/{entity_id}",
        json={"question_paper_section_id": str(other_section.id)},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["question_paper_section_id"] == str(other_section.id)


async def test_update_question_paper_question_mapping_rejects_nonexistent_section(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmadmin14", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="UPDBADSEC")
    section = await _create_section(
        db_session, question.institution_id, question.subject_id, code="UPDBADSEC1"
    )
    token = await _login(client, "qpqmadmin14")
    headers = _institution_headers(token, question.institution_id)

    created = await client.post(
        "/api/v1/question-paper-question-mappings",
        json=_payload(section.id, question.id),
        headers=headers,
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-paper-question-mappings/{entity_id}",
        json={"question_paper_section_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404


async def test_update_question_paper_question_mapping_accepts_new_question_in_same_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmadmin15", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="UPDQ")
    other_question = await _create_second_question(db_session, question, code="UPDQ2")
    section = await _create_section(
        db_session, question.institution_id, question.subject_id, code="UPDQ1"
    )
    token = await _login(client, "qpqmadmin15")
    headers = _institution_headers(token, question.institution_id)

    created = await client.post(
        "/api/v1/question-paper-question-mappings",
        json=_payload(section.id, question.id),
        headers=headers,
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-paper-question-mappings/{entity_id}",
        json={"question_id": str(other_question.id)},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["question_id"] == str(other_question.id)


async def test_update_question_paper_question_mapping_rejects_nonexistent_question(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmadmin16", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="UPDBADQ")
    section = await _create_section(
        db_session, question.institution_id, question.subject_id, code="UPDBADQ1"
    )
    token = await _login(client, "qpqmadmin16")
    headers = _institution_headers(token, question.institution_id)

    created = await client.post(
        "/api/v1/question-paper-question-mappings",
        json=_payload(section.id, question.id),
        headers=headers,
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-paper-question-mappings/{entity_id}",
        json={"question_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404


async def test_update_question_paper_question_mapping_rejects_duplicate_after_question_change(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpqmadmin17", role=seed_rbac["super_admin"])
    question = await _create_question(db_session, code="UPDDUPE")
    other_question = await _create_second_question(db_session, question, code="UPDDUPE2")
    section = await _create_section(
        db_session, question.institution_id, question.subject_id, code="UPDDUPE1"
    )
    token = await _login(client, "qpqmadmin17")
    headers = _institution_headers(token, question.institution_id)

    first = await client.post(
        "/api/v1/question-paper-question-mappings",
        json=_payload(section.id, question.id),
        headers=headers,
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/question-paper-question-mappings",
        json=_payload(section.id, other_question.id),
        headers=headers,
    )
    assert second.status_code == 201
    second_id = second.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-paper-question-mappings/{second_id}",
        json={"question_id": str(question.id)},
        headers=headers,
    )

    assert update_response.status_code == 409
