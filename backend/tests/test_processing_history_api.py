"""ProcessingHistory API tests: read-only endpoints + the `record()` service method directly."""

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
from app.models.program import Program
from app.models.section import Section
from app.models.subject import Subject
from app.models.subject_category import SubjectCategory
from app.services.processing_history_service import ProcessingHistoryService
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
    """Mirrors `test_ocr_jobs_api.py`'s `_create_answer_script` helper."""
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


async def test_record_persists_a_stage_transition(db_session: AsyncSession) -> None:
    script = await _create_answer_script(db_session, code="RECORD")
    service = ProcessingHistoryService(db_session)

    entry = await service.record(
        script.institution_id,
        script.id,
        stage="upload",
        from_status="uploading",
        to_status="uploaded",
        duration_ms=120,
        triggered_by="user",
    )
    await db_session.commit()

    assert entry.id is not None
    assert entry.answer_script_id == script.id
    assert entry.stage == "upload"
    assert entry.from_status == "uploading"
    assert entry.to_status == "uploaded"
    assert entry.duration_ms == 120
    assert entry.triggered_by == "user"


async def test_record_defaults_triggered_by_to_system(db_session: AsyncSession) -> None:
    script = await _create_answer_script(db_session, code="DEFAULTTRIGGER")
    service = ProcessingHistoryService(db_session)

    entry = await service.record(
        script.institution_id, script.id, stage="ocr", to_status="ocr_running"
    )
    await db_session.commit()

    assert entry.triggered_by == "system"
    assert entry.from_status is None


async def test_list_processing_history_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="phadmin1", role=seed_rbac["super_admin"])
    token = await _login(client, "phadmin1")

    response = await client.get("/api/v1/processing-history", headers=auth_headers(token))

    assert response.status_code == 422


async def test_non_privileged_role_cannot_list_processing_history(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="phstudent1", role=seed_rbac["student"])
    script = await _create_answer_script(db_session, code="FORBIDDEN")
    token = await _login(client, "phstudent1")

    response = await client.get(
        "/api/v1/processing-history", headers=_institution_headers(token, script.institution_id)
    )

    assert response.status_code == 403


async def test_get_nonexistent_processing_history_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="phadmin2", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="404")
    token = await _login(client, "phadmin2")

    response = await client.get(
        f"/api/v1/processing-history/{uuid.uuid4()}",
        headers=_institution_headers(token, script.institution_id),
    )

    assert response.status_code == 404


async def test_list_processing_history_filters_by_answer_script_id(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="phadmin3", role=seed_rbac["super_admin"])
    script_a = await _create_answer_script(db_session, code="FILTERA")
    script_b = await _create_answer_script(db_session, code="FILTERB")
    token = await _login(client, "phadmin3")
    headers = _institution_headers(token, script_a.institution_id)

    service = ProcessingHistoryService(db_session)
    await service.record(script_a.institution_id, script_a.id, stage="upload", to_status="uploaded")
    await service.record(script_a.institution_id, script_b.id, stage="upload", to_status="uploaded")
    await db_session.commit()

    response = await client.get(
        f"/api/v1/processing-history?answer_script_id={script_a.id}", headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["answer_script_id"] == str(script_a.id)


async def test_list_processing_history_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="phadmin4", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="LISTENV")
    token = await _login(client, "phadmin4")
    headers = _institution_headers(token, script.institution_id)

    service = ProcessingHistoryService(db_session)
    for i in range(5):
        await service.record(
            script.institution_id, script.id, stage=f"stage{i}", to_status="ocr_running"
        )
    await db_session.commit()

    response = await client.get("/api/v1/processing-history?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_get_processing_history_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="phadmin5", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="ROUNDTRIP")
    token = await _login(client, "phadmin5")
    headers = _institution_headers(token, script.institution_id)

    service = ProcessingHistoryService(db_session)
    entry = await service.record(
        script.institution_id, script.id, stage="storage", to_status="stored", triggered_by="system"
    )
    await db_session.commit()

    response = await client.get(f"/api/v1/processing-history/{entry.id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "storage"
    assert body["to_status"] == "stored"
    assert body["triggered_by"] == "system"
