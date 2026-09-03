"""ExtractedQuestion API tests: document-scoped filtering, update, and the
verify workflow (Module 06)."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.extracted_questions import router as extracted_questions_router
from app.core.config import get_settings
from app.main import app as fastapi_app
from app.models.assessment import Assessment
from app.models.assessment_status import AssessmentStatus
from app.models.assessment_type import AssessmentType
from app.models.batch import Batch
from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.exam import Exam
from app.models.extracted_question import ExtractedQuestion
from app.models.institution import Institution
from app.models.official_exam_document import OfficialExamDocument
from app.models.program import Program
from app.models.section import Section
from app.models.subject import Subject
from app.models.subject_category import SubjectCategory
from tests.conftest import auth_headers, create_test_user


@pytest.fixture(scope="module", autouse=True)
def _mount_extracted_questions_router():
    """
    `app/api/v1/router.py` is merged centrally by the Module 06 orchestrator
    once every task's endpoints exist -- this task must not edit it. Until
    that merge lands, mount this router directly onto the live app for the
    duration of this test module so these tests exercise a real
    request/response cycle, then unmount it, leaving the app exactly as it
    was for every other test module.
    """
    settings = get_settings()
    prefix = f"{settings.API_V1_PREFIX}/extracted-questions"
    already_mounted = any(
        getattr(route, "path", "").startswith(prefix) for route in fastapi_app.routes
    )
    if already_mounted:
        yield
        return
    original_routes = list(fastapi_app.routes)
    fastapi_app.include_router(extracted_questions_router, prefix=settings.API_V1_PREFIX)
    yield
    fastapi_app.router.routes = original_routes


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


async def _create_exam(db_session: AsyncSession, *, code: str) -> Exam:
    """Builds the full Institution->...->Exam parent chain (mirroring
    `tests/test_answer_scripts_api.py`'s `_create_exam_session` helper, but
    stopping at `Exam` — an `ExamSession`/`AnswerScript` isn't needed for
    `OfficialExamDocument`, which is exam-level not session-level)."""
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
    await db_session.commit()
    await db_session.refresh(exam)
    return exam


async def _create_document(db_session: AsyncSession, *, code: str) -> OfficialExamDocument:
    exam = await _create_exam(db_session, code=code)
    uploader = await create_test_user(db_session, username=f"uploader_{code.lower()}")
    document = OfficialExamDocument(
        institution_id=exam.institution_id,
        exam_id=exam.id,
        uploaded_by=uploader.id,
        document_type="question_paper",
        original_filename=f"{code}.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        ocr_status="completed",
        verification_status="not_started",
    )
    db_session.add(document)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(document)
    return document


async def _create_extracted_question(
    db_session: AsyncSession,
    document: OfficialExamDocument,
    *,
    question_number: str,
    **overrides: object,
) -> ExtractedQuestion:
    defaults: dict[str, object] = {
        "institution_id": document.institution_id,
        "document_id": document.id,
        "question_number": question_number,
        "question_text": f"What is question {question_number}?",
        "raw_ocr_text": f"raw ocr text {question_number}",
        "detected_marks": Decimal("5.00"),
        "display_order": int(question_number),
    }
    defaults.update(overrides)
    entity = ExtractedQuestion(**defaults)  # type: ignore[arg-type]
    db_session.add(entity)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(entity)
    return entity


async def test_list_extracted_questions_filters_by_document_id(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eqadmin1", role=seed_rbac["super_admin"])
    document_a = await _create_document(db_session, code="DOCA")
    document_b = await _create_document(db_session, code="DOCB")
    await _create_extracted_question(db_session, document_a, question_number="1")
    await _create_extracted_question(db_session, document_a, question_number="2")
    await _create_extracted_question(db_session, document_b, question_number="1")
    token = await _login(client, "eqadmin1")

    response = await client.get(
        f"/api/v1/extracted-questions?document_id={document_a.id}",
        headers=_institution_headers(token, document_a.institution_id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert all(item["document_id"] == str(document_a.id) for item in body["items"])


async def test_list_extracted_questions_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eqadmin2", role=seed_rbac["super_admin"])
    token = await _login(client, "eqadmin2")

    response = await client.get("/api/v1/extracted-questions", headers=auth_headers(token))

    assert response.status_code == 422


async def test_non_privileged_role_cannot_list_extracted_questions(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eqstudent1", role=seed_rbac["student"])
    document = await _create_document(db_session, code="FORBIDDEN")
    token = await _login(client, "eqstudent1")

    response = await client.get(
        "/api/v1/extracted-questions",
        headers=_institution_headers(token, document.institution_id),
    )

    assert response.status_code == 403


async def test_get_nonexistent_extracted_question_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eqadmin3", role=seed_rbac["super_admin"])
    document = await _create_document(db_session, code="404")
    token = await _login(client, "eqadmin3")

    response = await client.get(
        f"/api/v1/extracted-questions/{uuid.uuid4()}",
        headers=_institution_headers(token, document.institution_id),
    )

    assert response.status_code == 404


async def test_get_extracted_question_returns_full_field_mirror(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eqadmin4", role=seed_rbac["super_admin"])
    document = await _create_document(db_session, code="GET")
    entity = await _create_extracted_question(db_session, document, question_number="1")
    token = await _login(client, "eqadmin4")

    response = await client.get(
        f"/api/v1/extracted-questions/{entity.id}",
        headers=_institution_headers(token, document.institution_id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["question_number"] == "1"
    assert body["question_text"] == "What is question 1?"
    assert body["verification_status"] == "pending"
    assert body["verified_by"] is None
    assert body["verified_at"] is None


async def test_update_extracted_question_only_allows_editable_fields(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eqadmin5", role=seed_rbac["super_admin"])
    document = await _create_document(db_session, code="UPDATE")
    entity = await _create_extracted_question(db_session, document, question_number="1")
    token = await _login(client, "eqadmin5")
    headers = _institution_headers(token, document.institution_id)

    response = await client.patch(
        f"/api/v1/extracted-questions/{entity.id}",
        json={"question_text": "Edited question text", "final_marks": "4.50"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["question_text"] == "Edited question text"
    assert body["final_marks"] == "4.50"
    # raw_ocr_text is immutable — untouched by the update.
    assert body["raw_ocr_text"] == "raw ocr text 1"


async def test_update_extracted_question_rejects_unknown_field(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eqadmin6", role=seed_rbac["super_admin"])
    document = await _create_document(db_session, code="BADFIELD")
    entity = await _create_extracted_question(db_session, document, question_number="1")
    token = await _login(client, "eqadmin6")
    headers = _institution_headers(token, document.institution_id)

    response = await client.patch(
        f"/api/v1/extracted-questions/{entity.id}",
        json={"question_number": "99"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_non_privileged_role_cannot_update_extracted_question(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eqstudent2", role=seed_rbac["student"])
    document = await _create_document(db_session, code="UPDATEFORBIDDEN")
    entity = await _create_extracted_question(db_session, document, question_number="1")
    token = await _login(client, "eqstudent2")
    headers = _institution_headers(token, document.institution_id)

    response = await client.patch(
        f"/api/v1/extracted-questions/{entity.id}",
        json={"question_text": "Nope"},
        headers=headers,
    )

    assert response.status_code == 403


async def test_verify_extracted_question_sets_status_actor_and_timestamp(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    admin = await create_test_user(db_session, username="eqadmin7", role=seed_rbac["super_admin"])
    document = await _create_document(db_session, code="VERIFY")
    entity = await _create_extracted_question(db_session, document, question_number="1")
    token = await _login(client, "eqadmin7")
    headers = _institution_headers(token, document.institution_id)

    response = await client.post(f"/api/v1/extracted-questions/{entity.id}/verify", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["verification_status"] == "verified"
    assert body["verified_by"] == str(admin.id)
    assert body["verified_at"] is not None


async def test_non_privileged_role_cannot_verify_extracted_question(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eqstudent3", role=seed_rbac["student"])
    document = await _create_document(db_session, code="VERIFYFORBIDDEN")
    entity = await _create_extracted_question(db_session, document, question_number="1")
    token = await _login(client, "eqstudent3")
    headers = _institution_headers(token, document.institution_id)

    response = await client.post(f"/api/v1/extracted-questions/{entity.id}/verify", headers=headers)

    assert response.status_code == 403


async def test_verify_nonexistent_extracted_question_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eqadmin8", role=seed_rbac["super_admin"])
    document = await _create_document(db_session, code="VERIFY404")
    token = await _login(client, "eqadmin8")

    response = await client.post(
        f"/api/v1/extracted-questions/{uuid.uuid4()}/verify",
        headers=_institution_headers(token, document.institution_id),
    )

    assert response.status_code == 404


async def test_list_extracted_questions_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eqadmin9", role=seed_rbac["super_admin"])
    document = await _create_document(db_session, code="LISTENV")
    for i in range(1, 6):
        await _create_extracted_question(db_session, document, question_number=str(i))
    token = await _login(client, "eqadmin9")
    headers = _institution_headers(token, document.institution_id)

    response = await client.get("/api/v1/extracted-questions?page=1&page_size=2", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3
