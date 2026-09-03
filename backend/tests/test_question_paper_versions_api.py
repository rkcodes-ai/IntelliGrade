"""QuestionPaperVersion API tests: snapshot creation (nested), browsing (standalone)."""

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


async def _create_assessment(db_session: AsyncSession, *, code: str = "ASM1") -> Assessment:
    """Builds the full Institution->...->Assessment parent chain, mirroring
    `tests/test_assessment_configurations_api.py`'s `_create_assessment` helper."""
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
    await db_session.commit()
    await db_session.refresh(assessment)
    return assessment


async def test_create_question_paper_version_snapshot_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    admin = await create_test_user(db_session, username="qpvadmin1", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="CREATE")
    token = await _login(client, "qpvadmin1")
    headers = _institution_headers(token, assessment.institution_id)

    paper_response = await client.post(
        "/api/v1/question-papers",
        json={
            "assessment_id": str(assessment.id),
            "name": "Midterm Question Paper",
            "total_marks": "100.00",
        },
        headers=headers,
    )
    assert paper_response.status_code == 201
    paper_id = paper_response.json()["id"]

    version_response = await client.post(
        f"/api/v1/question-papers/{paper_id}/versions",
        json={"change_reason": "Initial snapshot"},
        headers=headers,
    )

    assert version_response.status_code == 201
    body = version_response.json()
    assert body["question_paper_id"] == paper_id
    assert body["version_number"] == 1
    assert body["change_reason"] == "Initial snapshot"
    assert body["changed_by"] == str(admin.id)
    assert body["snapshot"]["name"] == "Midterm Question Paper"
    assert body["snapshot"]["approval_status"] == "draft"


async def test_create_question_paper_version_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpvadmin2", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="NOHEADER")
    token = await _login(client, "qpvadmin2")
    headers = _institution_headers(token, assessment.institution_id)

    paper_response = await client.post(
        "/api/v1/question-papers",
        json={
            "assessment_id": str(assessment.id),
            "name": "Paper",
            "total_marks": "100.00",
        },
        headers=headers,
    )
    paper_id = paper_response.json()["id"]

    response = await client.post(
        f"/api/v1/question-papers/{paper_id}/versions",
        json={"change_reason": "no header"},
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_question_paper_version_rejects_nonexistent_paper(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpvadmin3", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="BADPARENT")
    token = await _login(client, "qpvadmin3")
    headers = _institution_headers(token, assessment.institution_id)

    response = await client.post(
        f"/api/v1/question-papers/{uuid.uuid4()}/versions",
        json={"change_reason": "missing parent"},
        headers=headers,
    )

    assert response.status_code == 404


async def test_non_privileged_role_cannot_create_question_paper_version(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpvadmin4", role=seed_rbac["super_admin"])
    await create_test_user(db_session, username="qpvstudent1", role=seed_rbac["student"])
    assessment = await _create_assessment(db_session, code="FORBIDDEN")
    admin_token = await _login(client, "qpvadmin4")
    student_token = await _login(client, "qpvstudent1")
    admin_headers = _institution_headers(admin_token, assessment.institution_id)

    paper_response = await client.post(
        "/api/v1/question-papers",
        json={
            "assessment_id": str(assessment.id),
            "name": "Paper",
            "total_marks": "100.00",
        },
        headers=admin_headers,
    )
    paper_id = paper_response.json()["id"]

    student_headers = _institution_headers(student_token, assessment.institution_id)
    response = await client.post(
        f"/api/v1/question-papers/{paper_id}/versions",
        json={"change_reason": "not allowed"},
        headers=student_headers,
    )

    assert response.status_code == 403


async def test_get_nonexistent_question_paper_version_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpvadmin5", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="GETMISSING")
    token = await _login(client, "qpvadmin5")

    response = await client.get(
        f"/api/v1/question-paper-versions/{uuid.uuid4()}",
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 404


async def test_snapshot_twice_increments_version_number(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpvadmin6", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="TWOSNAPSHOTS")
    token = await _login(client, "qpvadmin6")
    headers = _institution_headers(token, assessment.institution_id)

    paper_response = await client.post(
        "/api/v1/question-papers",
        json={
            "assessment_id": str(assessment.id),
            "name": "Paper v1",
            "total_marks": "100.00",
        },
        headers=headers,
    )
    paper_id = paper_response.json()["id"]

    first_snapshot = await client.post(
        f"/api/v1/question-papers/{paper_id}/versions",
        json={"change_reason": "first"},
        headers=headers,
    )
    assert first_snapshot.status_code == 201
    assert first_snapshot.json()["version_number"] == 1

    # Change the paper's content between snapshots so the two snapshots differ.
    await client.patch(
        f"/api/v1/question-papers/{paper_id}", json={"name": "Paper v2"}, headers=headers
    )

    second_snapshot = await client.post(
        f"/api/v1/question-papers/{paper_id}/versions",
        json={"change_reason": "second"},
        headers=headers,
    )
    assert second_snapshot.status_code == 201
    assert second_snapshot.json()["version_number"] == 2
    assert second_snapshot.json()["snapshot"]["name"] == "Paper v2"


async def test_list_question_paper_versions_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpvadmin7", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="LIST")
    token = await _login(client, "qpvadmin7")
    headers = _institution_headers(token, assessment.institution_id)

    paper_response = await client.post(
        "/api/v1/question-papers",
        json={
            "assessment_id": str(assessment.id),
            "name": "Paper",
            "total_marks": "100.00",
        },
        headers=headers,
    )
    paper_id = paper_response.json()["id"]

    for i in range(3):
        response = await client.post(
            f"/api/v1/question-papers/{paper_id}/versions",
            json={"change_reason": f"snapshot {i}"},
            headers=headers,
        )
        assert response.status_code == 201

    list_response = await client.get(
        "/api/v1/question-paper-versions?page=1&page_size=2", headers=headers
    )
    assert list_response.status_code == 200
    body = list_response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 3
    assert body["total_pages"] == 2

    get_response = await client.get(
        f"/api/v1/question-paper-versions/{body['items'][0]['id']}", headers=headers
    )
    assert get_response.status_code == 200
