"""UploadJob API tests: read-only endpoints over rows created internally
by AnswerScriptService.upload()."""

import uuid
from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.assessment_status import AssessmentStatus
from app.models.assessment_type import AssessmentType
from app.models.batch import Batch
from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.exam import Exam
from app.models.exam_session import ExamSession
from app.models.institution import Institution
from app.models.program import Program
from app.models.section import Section
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


async def _create_exam_session(db_session: AsyncSession, *, code: str) -> ExamSession:
    """Mirrors `test_answer_scripts_api.py`'s `_create_exam_session` helper."""
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

    batch = Batch(
        institution_id=institution.id,
        course_id=course.id,
        name=f"Batch {code}",
        start_year=2024,
        end_year=2028,
    )
    db_session.add(batch)
    await db_session.flush()

    section = Section(
        institution_id=institution.id, batch_id=batch.id, name=f"Sec-{code}", max_capacity=60
    )
    db_session.add(section)
    await db_session.flush()

    exam = Exam(
        institution_id=institution.id,
        assessment_id=assessment.id,
        section_id=section.id,
        name=f"Exam {code}",
        exam_date=date(2026, 8, 10),
    )
    db_session.add(exam)
    await db_session.flush()

    student = await create_test_user(db_session, username=f"student_{code.lower()}")
    exam_session = ExamSession(
        institution_id=institution.id, exam_id=exam.id, student_user_id=student.id
    )
    db_session.add(exam_session)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(exam_session)
    return exam_session


async def test_upload_answer_script_creates_a_completed_upload_job(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ujadmin1", role=seed_rbac["super_admin"])
    exam_session = await _create_exam_session(db_session, code="CREATE")
    token = await _login(client, "ujadmin1")
    headers = _institution_headers(token, exam_session.institution_id)

    upload_response = await client.post(
        "/api/v1/answer-scripts",
        data={"exam_session_id": str(exam_session.id)},
        files={"file": ("script.pdf", b"pdf bytes", "application/pdf")},
        headers=headers,
    )
    assert upload_response.status_code == 201
    script_id = upload_response.json()["id"]

    response = await client.get(
        f"/api/v1/upload-jobs?answer_script_id={script_id}", headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    job = body["items"][0]
    assert job["answer_script_id"] == script_id
    assert job["status"] == "completed"
    assert job["chunks_received"] == 1
    assert job["total_chunks"] == 1
    assert job["bytes_received"] == len(b"pdf bytes")


async def test_list_upload_jobs_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ujadmin2", role=seed_rbac["super_admin"])
    token = await _login(client, "ujadmin2")

    response = await client.get("/api/v1/upload-jobs", headers=auth_headers(token))

    assert response.status_code == 422


async def test_non_privileged_role_cannot_list_upload_jobs(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ujstudent1", role=seed_rbac["student"])
    exam_session = await _create_exam_session(db_session, code="FORBIDDEN")
    token = await _login(client, "ujstudent1")

    response = await client.get(
        "/api/v1/upload-jobs", headers=_institution_headers(token, exam_session.institution_id)
    )

    assert response.status_code == 403


async def test_get_nonexistent_upload_job_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ujadmin3", role=seed_rbac["super_admin"])
    exam_session = await _create_exam_session(db_session, code="404")
    token = await _login(client, "ujadmin3")

    response = await client.get(
        f"/api/v1/upload-jobs/{uuid.uuid4()}",
        headers=_institution_headers(token, exam_session.institution_id),
    )

    assert response.status_code == 404


async def test_get_upload_job_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ujadmin4", role=seed_rbac["super_admin"])
    exam_session = await _create_exam_session(db_session, code="ROUNDTRIP")
    token = await _login(client, "ujadmin4")
    headers = _institution_headers(token, exam_session.institution_id)

    upload_response = await client.post(
        "/api/v1/answer-scripts",
        data={"exam_session_id": str(exam_session.id)},
        files={"file": ("script.pdf", b"more pdf bytes", "application/pdf")},
        headers=headers,
    )
    script_id = upload_response.json()["id"]

    list_response = await client.get(
        f"/api/v1/upload-jobs?answer_script_id={script_id}", headers=headers
    )
    job_id = list_response.json()["items"][0]["id"]

    response = await client.get(f"/api/v1/upload-jobs/{job_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == job_id


async def test_list_upload_jobs_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ujadmin5", role=seed_rbac["super_admin"])
    exam_session = await _create_exam_session(db_session, code="LISTENV")
    token = await _login(client, "ujadmin5")
    headers = _institution_headers(token, exam_session.institution_id)

    for i in range(5):
        response = await client.post(
            "/api/v1/answer-scripts",
            data={"exam_session_id": str(exam_session.id)},
            files={"file": (f"script{i}.pdf", f"content {i}".encode(), "application/pdf")},
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/upload-jobs?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3
