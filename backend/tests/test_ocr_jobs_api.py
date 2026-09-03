"""OCRJob API tests: CRUD, tenancy, and cancel-state-guard business rules."""

import uuid
from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer_script import AnswerScript
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
from app.models.ocr_provider import OCRProvider
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


async def _create_answer_script(db_session: AsyncSession, *, code: str) -> AnswerScript:
    """Builds the full Institution->...->Exam->ExamSession parent chain
    (mirroring `test_exam_sessions_api.py`'s `_create_exam` helper) plus an
    uploader `User` and a persisted `AnswerScript`."""
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
    uploader = await create_test_user(db_session, username=f"uploader_{code.lower()}")

    exam_session = ExamSession(
        institution_id=institution.id, exam_id=exam.id, student_user_id=student.id
    )
    db_session.add(exam_session)
    await db_session.flush()

    answer_script = AnswerScript(
        institution_id=institution.id,
        exam_session_id=exam_session.id,
        uploaded_by=uploader.id,
        original_filename=f"script_{code}.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        checksum_sha256=f"checksum-{code}",
        status="stored",
        is_active=True,
    )
    db_session.add(answer_script)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(answer_script)
    return answer_script


async def _create_provider(
    db_session: AsyncSession, *, code: str, **overrides: object
) -> OCRProvider:
    defaults: dict[str, object] = {
        "code": code,
        "name": code.title(),
        "is_enabled": True,
        "is_implemented": True,
        "is_default": False,
    }
    defaults.update(overrides)
    provider = OCRProvider(**defaults)  # type: ignore[arg-type]
    db_session.add(provider)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(provider)
    return provider


def _payload(
    answer_script_id: uuid.UUID, ocr_provider_id: uuid.UUID, **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "answer_script_id": str(answer_script_id),
        "ocr_provider_id": str(ocr_provider_id),
    }
    payload.update(overrides)
    return payload


async def test_create_ocr_job_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ojadmin1", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="CREATE")
    provider = await _create_provider(db_session, code="tesseract_j1")
    token = await _login(client, "ojadmin1")

    response = await client.post(
        "/api/v1/ocr-jobs",
        json=_payload(script.id, provider.id),
        headers=_institution_headers(token, script.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["answer_script_id"] == str(script.id)
    assert body["ocr_provider_id"] == str(provider.id)
    assert body["status"] == "queued"
    assert body["priority"] == 5
    assert body["retry_count"] == 0


async def test_create_ocr_job_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ojadmin2", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="NOHEADER")
    provider = await _create_provider(db_session, code="tesseract_j2")
    token = await _login(client, "ojadmin2")

    response = await client.post(
        "/api/v1/ocr-jobs", json=_payload(script.id, provider.id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_non_privileged_role_cannot_create_ocr_job(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ojstudent1", role=seed_rbac["student"])
    script = await _create_answer_script(db_session, code="FORBIDDEN")
    provider = await _create_provider(db_session, code="tesseract_j3")
    token = await _login(client, "ojstudent1")

    response = await client.post(
        "/api/v1/ocr-jobs",
        json=_payload(script.id, provider.id),
        headers=_institution_headers(token, script.institution_id),
    )

    assert response.status_code == 403


async def test_get_nonexistent_ocr_job_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ojadmin3", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="404")
    token = await _login(client, "ojadmin3")

    response = await client.get(
        f"/api/v1/ocr-jobs/{uuid.uuid4()}",
        headers=_institution_headers(token, script.institution_id),
    )

    assert response.status_code == 404


async def test_ocr_job_cancel_from_queued_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ojadmin4", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="CANCEL")
    provider = await _create_provider(db_session, code="tesseract_j4")
    token = await _login(client, "ojadmin4")
    headers = _institution_headers(token, script.institution_id)

    created = await client.post(
        "/api/v1/ocr-jobs", json=_payload(script.id, provider.id), headers=headers
    )
    assert created.status_code == 201
    job_id = created.json()["id"]

    cancel_response = await client.post(f"/api/v1/ocr-jobs/{job_id}/cancel", headers=headers)
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"


async def test_ocr_job_cancel_rejects_already_cancelled(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ojadmin5", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="DOUBLECANCEL")
    provider = await _create_provider(db_session, code="tesseract_j5")
    token = await _login(client, "ojadmin5")
    headers = _institution_headers(token, script.institution_id)

    created = await client.post(
        "/api/v1/ocr-jobs", json=_payload(script.id, provider.id), headers=headers
    )
    job_id = created.json()["id"]

    first_cancel = await client.post(f"/api/v1/ocr-jobs/{job_id}/cancel", headers=headers)
    assert first_cancel.status_code == 200

    second_cancel = await client.post(f"/api/v1/ocr-jobs/{job_id}/cancel", headers=headers)
    assert second_cancel.status_code == 409


async def test_list_ocr_jobs_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ojadmin6", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="LISTENV")
    provider = await _create_provider(db_session, code="tesseract_j6")
    token = await _login(client, "ojadmin6")
    headers = _institution_headers(token, script.institution_id)

    for _ in range(5):
        response = await client.post(
            "/api/v1/ocr-jobs", json=_payload(script.id, provider.id), headers=headers
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/ocr-jobs?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3
