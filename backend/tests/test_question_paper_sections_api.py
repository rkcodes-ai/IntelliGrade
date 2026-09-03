"""QuestionPaperSection API tests: CRUD, tenancy, soft-delete/restore.

`QuestionPaper` is a sibling Module 04 model built by another agent in the
same implementation wave; `_create_question_paper` builds its full
Institution->Campus->Department->Program->Course->SubjectCategory->
Subject->AssessmentType/Status->Assessment->QuestionPaper parent chain
directly via the ORM, mirroring `test_assessment_configurations_api.py`'s
`_create_assessment` helper (`QuestionPaper` additionally requires
`assessment_id`, `name`, `total_marks`).
"""

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.assessment_status import AssessmentStatus
from app.models.assessment_type import AssessmentType
from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.institution import Institution
from app.models.program import Program
from app.models.question_paper import QuestionPaper
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


async def _create_question_paper(db_session: AsyncSession, *, code: str) -> QuestionPaper:
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

    assessment_type = AssessmentType(
        institution_id=institution.id, code=f"AT-{code}", name=f"Type {code}"
    )
    db_session.add(assessment_type)
    await db_session.flush()

    assessment_status = AssessmentStatus(
        institution_id=institution.id, code=f"AS-{code}", name=f"Status {code}"
    )
    db_session.add(assessment_status)
    await db_session.flush()

    assessment = Assessment(
        institution_id=institution.id,
        subject_id=subject.id,
        assessment_type_id=assessment_type.id,
        assessment_status_id=assessment_status.id,
        name=f"Assessment {code}",
    )
    db_session.add(assessment)
    await db_session.flush()

    paper = QuestionPaper(
        institution_id=institution.id,
        assessment_id=assessment.id,
        name=f"Paper {code}",
        total_marks=Decimal("100.00"),
    )
    db_session.add(paper)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(paper)
    return paper


async def _create_second_question_paper(
    db_session: AsyncSession, paper: QuestionPaper, *, code: str
) -> QuestionPaper:
    """A second `QuestionPaper` in the same institution (reusing
    `assessment_id`), so update tests can PATCH `question_paper_id` to a
    different-but-still-valid parent within the same tenant."""
    second = QuestionPaper(
        institution_id=paper.institution_id,
        assessment_id=paper.assessment_id,
        name=f"Paper {code}",
        total_marks=Decimal("100.00"),
    )
    db_session.add(second)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(second)
    return second


def _payload(question_paper_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "question_paper_id": str(question_paper_id),
        "name": "Section A",
        "instructions": "Answer all questions.",
        "marks_per_question": "2.00",
        "display_order": 0,
    }
    payload.update(overrides)
    return payload


async def test_create_question_paper_section_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpsadmin1", role=seed_rbac["super_admin"])
    paper = await _create_question_paper(db_session, code="CREATE")
    token = await _login(client, "qpsadmin1")

    response = await client.post(
        "/api/v1/question-paper-sections",
        json=_payload(paper.id),
        headers=_institution_headers(token, paper.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["question_paper_id"] == str(paper.id)
    assert body["name"] == "Section A"
    assert body["display_order"] == 0
    assert body["is_active"] is True


async def test_create_question_paper_section_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpsadmin2", role=seed_rbac["super_admin"])
    paper = await _create_question_paper(db_session, code="NOHEADER")
    token = await _login(client, "qpsadmin2")

    response = await client.post(
        "/api/v1/question-paper-sections", json=_payload(paper.id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_question_paper_section_rejects_nonexistent_question_paper(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpsadmin3", role=seed_rbac["super_admin"])
    paper = await _create_question_paper(db_session, code="BADPARENT")
    token = await _login(client, "qpsadmin3")

    response = await client.post(
        "/api/v1/question-paper-sections",
        json=_payload(uuid.uuid4()),
        headers=_institution_headers(token, paper.institution_id),
    )

    assert response.status_code == 404


async def test_non_privileged_role_cannot_create_question_paper_section(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpsstudent1", role=seed_rbac["student"])
    paper = await _create_question_paper(db_session, code="FORBIDDEN")
    token = await _login(client, "qpsstudent1")

    response = await client.post(
        "/api/v1/question-paper-sections",
        json=_payload(paper.id),
        headers=_institution_headers(token, paper.institution_id),
    )

    assert response.status_code == 403


async def test_question_paper_section_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpsadmin4", role=seed_rbac["super_admin"])
    paper = await _create_question_paper(db_session, code="ROUNDTRIP")
    token = await _login(client, "qpsadmin4")
    headers = _institution_headers(token, paper.institution_id)

    create_response = await client.post(
        "/api/v1/question-paper-sections", json=_payload(paper.id), headers=headers
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]
    original_updated_at = create_response.json()["updated_at"]

    get_response = await client.get(f"/api/v1/question-paper-sections/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Section A"

    update_response = await client.patch(
        f"/api/v1/question-paper-sections/{entity_id}",
        json={"name": "Section B", "display_order": 1},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert updated_body["name"] == "Section B"
    assert updated_body["display_order"] == 1
    # SQLite's func.now() has only whole-second resolution, so a fast
    # create-then-update in the same test can legitimately land in the same
    # second — assert non-decreasing, not strict inequality.
    assert updated_body["updated_at"] >= original_updated_at

    delete_response = await client.delete(
        f"/api/v1/question-paper-sections/{entity_id}", headers=headers
    )
    assert delete_response.status_code == 204

    get_after_delete = await client.get(
        f"/api/v1/question-paper-sections/{entity_id}", headers=headers
    )
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/question-paper-sections/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/question-paper-sections/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(
        f"/api/v1/question-paper-sections/{entity_id}", headers=headers
    )
    assert get_after_restore.status_code == 200


async def test_question_paper_section_get_nonexistent_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpsadmin5", role=seed_rbac["super_admin"])
    paper = await _create_question_paper(db_session, code="404")
    token = await _login(client, "qpsadmin5")

    response = await client.get(
        f"/api/v1/question-paper-sections/{uuid.uuid4()}",
        headers=_institution_headers(token, paper.institution_id),
    )
    assert response.status_code == 404


async def test_list_question_paper_sections_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpsadmin6", role=seed_rbac["super_admin"])
    paper = await _create_question_paper(db_session, code="LIST")
    token = await _login(client, "qpsadmin6")
    headers = _institution_headers(token, paper.institution_id)

    for i in range(5):
        response = await client.post(
            "/api/v1/question-paper-sections",
            json=_payload(paper.id, name=f"Section {i}", display_order=i),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get(
        "/api/v1/question-paper-sections?page=1&page_size=2", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] >= 5


async def test_bulk_create_question_paper_sections_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpsadmin7", role=seed_rbac["super_admin"])
    paper = await _create_question_paper(db_session, code="BULKOK")
    token = await _login(client, "qpsadmin7")
    headers = _institution_headers(token, paper.institution_id)

    response = await client.post(
        "/api/v1/question-paper-sections/bulk",
        json=[
            _payload(paper.id, name="Bulk Section One"),
            _payload(paper.id, name="Bulk Section Two"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert body["errors"] == []


async def test_bulk_create_question_paper_sections_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpsadmin8", role=seed_rbac["super_admin"])
    paper = await _create_question_paper(db_session, code="BULKERR")
    token = await _login(client, "qpsadmin8")
    headers = _institution_headers(token, paper.institution_id)

    response = await client.post(
        "/api/v1/question-paper-sections/bulk",
        json=[
            _payload(paper.id, name="Valid Section"),
            _payload(uuid.uuid4(), name="Missing Paper Section"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["name"] == "Missing Paper Section"


async def test_export_question_paper_sections_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpsadmin9", role=seed_rbac["super_admin"])
    paper = await _create_question_paper(db_session, code="EXPORT")
    token = await _login(client, "qpsadmin9")
    headers = _institution_headers(token, paper.institution_id)

    response = await client.get("/api/v1/question-paper-sections/export", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_question_paper_sections_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpsadmin10", role=seed_rbac["super_admin"])
    paper = await _create_question_paper(db_session, code="IMPORT")
    token = await _login(client, "qpsadmin10")
    headers = _institution_headers(token, paper.institution_id)

    response = await client.post("/api/v1/question-paper-sections/import", headers=headers)

    assert response.status_code == 202
    assert response.json()["status"] == "not_implemented"


async def test_update_question_paper_section_accepts_new_paper_in_same_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpsadmin11", role=seed_rbac["super_admin"])
    paper = await _create_question_paper(db_session, code="UPDFK")
    other_paper = await _create_second_question_paper(db_session, paper, code="UPDFK2")
    token = await _login(client, "qpsadmin11")
    headers = _institution_headers(token, paper.institution_id)

    created = await client.post(
        "/api/v1/question-paper-sections", json=_payload(paper.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-paper-sections/{entity_id}",
        json={"question_paper_id": str(other_paper.id)},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["question_paper_id"] == str(other_paper.id)


async def test_update_question_paper_section_rejects_nonexistent_paper(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpsadmin12", role=seed_rbac["super_admin"])
    paper = await _create_question_paper(db_session, code="UPDBAD")
    token = await _login(client, "qpsadmin12")
    headers = _institution_headers(token, paper.institution_id)

    created = await client.post(
        "/api/v1/question-paper-sections", json=_payload(paper.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-paper-sections/{entity_id}",
        json={"question_paper_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404
