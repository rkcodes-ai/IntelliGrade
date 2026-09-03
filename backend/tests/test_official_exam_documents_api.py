"""OfficialExamDocument API tests: multipart upload, tenancy, duplicate
detection, retry/cancel workflow. Mirrors `test_answer_scripts_api.py`'s
conventions, stopping the parent chain at `Exam` (exam-level, not
per-student — see ADR-035)."""

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


async def _create_exam(db_session: AsyncSession, *, code: str) -> Exam:
    """Builds the Institution->...->Exam parent chain, stopping short of
    `ExamSession` (per-student, not needed here — see ADR-035)."""
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


def _upload_files(filename: str = "qp.pdf", content: bytes = b"%PDF-1.4 fake pdf content"):
    return {"file": (filename, content, "application/pdf")}


async def test_upload_official_exam_document_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedadmin1", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="UPLOAD")
    token = await _login(client, "oedadmin1")

    response = await client.post(
        "/api/v1/official-exam-documents",
        data={"exam_id": str(exam.id), "document_type": "question_paper"},
        files=_upload_files(),
        headers=_institution_headers(token, exam.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["exam_id"] == str(exam.id)
    assert body["document_type"] == "question_paper"
    assert body["original_filename"] == "qp.pdf"
    assert body["ocr_status"] == "stored"
    assert body["verification_status"] == "not_started"
    assert body["storage_key"] is not None
    assert body["checksum_sha256"] is not None


async def test_upload_official_exam_document_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedadmin2", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="NOHEADER")
    token = await _login(client, "oedadmin2")

    response = await client.post(
        "/api/v1/official-exam-documents",
        data={"exam_id": str(exam.id), "document_type": "question_paper"},
        files=_upload_files(),
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_non_privileged_role_cannot_upload_official_exam_document(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedstudent1", role=seed_rbac["student"])
    exam = await _create_exam(db_session, code="FORBIDDEN")
    token = await _login(client, "oedstudent1")

    response = await client.post(
        "/api/v1/official-exam-documents",
        data={"exam_id": str(exam.id), "document_type": "question_paper"},
        files=_upload_files(),
        headers=_institution_headers(token, exam.institution_id),
    )

    assert response.status_code == 403


async def test_upload_official_exam_document_rejects_nonexistent_exam(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedadmin3", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="BADPARENT")
    token = await _login(client, "oedadmin3")

    response = await client.post(
        "/api/v1/official-exam-documents",
        data={"exam_id": str(uuid.uuid4()), "document_type": "question_paper"},
        files=_upload_files(),
        headers=_institution_headers(token, exam.institution_id),
    )

    assert response.status_code == 404


async def test_upload_official_exam_document_rejects_invalid_document_type(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedadmin4", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="BADTYPE")
    token = await _login(client, "oedadmin4")

    response = await client.post(
        "/api/v1/official-exam-documents",
        data={"exam_id": str(exam.id), "document_type": "not_a_real_type"},
        files=_upload_files(),
        headers=_institution_headers(token, exam.institution_id),
    )

    assert response.status_code == 422


async def test_upload_official_exam_document_rejects_duplicate(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedadmin5", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="DUPLICATE")
    token = await _login(client, "oedadmin5")
    headers = _institution_headers(token, exam.institution_id)

    first = await client.post(
        "/api/v1/official-exam-documents",
        data={"exam_id": str(exam.id), "document_type": "question_paper"},
        files=_upload_files(content=b"identical content"),
        headers=headers,
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/official-exam-documents",
        data={"exam_id": str(exam.id), "document_type": "question_paper"},
        files=_upload_files(content=b"identical content"),
        headers=headers,
    )
    assert second.status_code == 409


async def test_upload_official_exam_document_allows_duplicate_when_overridden(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedadmin6", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="ALLOWDUP")
    token = await _login(client, "oedadmin6")
    headers = _institution_headers(token, exam.institution_id)

    first = await client.post(
        "/api/v1/official-exam-documents",
        data={"exam_id": str(exam.id), "document_type": "question_paper"},
        files=_upload_files(content=b"same bytes"),
        headers=headers,
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/official-exam-documents",
        data={
            "exam_id": str(exam.id),
            "document_type": "question_paper",
            "allow_duplicate": "true",
        },
        files=_upload_files(content=b"same bytes"),
        headers=headers,
    )
    assert second.status_code == 201


async def test_get_nonexistent_official_exam_document_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedadmin7", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="404")
    token = await _login(client, "oedadmin7")

    response = await client.get(
        f"/api/v1/official-exam-documents/{uuid.uuid4()}",
        headers=_institution_headers(token, exam.institution_id),
    )

    assert response.status_code == 404


async def test_official_exam_document_download_returns_presigned_url(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedadmin8", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="DOWNLOAD")
    token = await _login(client, "oedadmin8")
    headers = _institution_headers(token, exam.institution_id)

    created = await client.post(
        "/api/v1/official-exam-documents",
        data={"exam_id": str(exam.id), "document_type": "model_answer"},
        files=_upload_files(filename="ma.pdf"),
        headers=headers,
    )
    document_id = created.json()["id"]

    response = await client.get(
        f"/api/v1/official-exam-documents/{document_id}/download", headers=headers
    )

    assert response.status_code == 200
    assert response.json()["url"].startswith("http://fake-storage.test/")


async def test_official_exam_document_update_is_active_only(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedadmin9", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="UPDATE")
    token = await _login(client, "oedadmin9")
    headers = _institution_headers(token, exam.institution_id)

    created = await client.post(
        "/api/v1/official-exam-documents",
        data={"exam_id": str(exam.id), "document_type": "mark_scheme"},
        files=_upload_files(filename="ms.pdf"),
        headers=headers,
    )
    document_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/official-exam-documents/{document_id}", json={"is_active": False}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_official_exam_document_soft_delete_and_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedadmin10", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="ROUNDTRIP")
    token = await _login(client, "oedadmin10")
    headers = _institution_headers(token, exam.institution_id)

    created = await client.post(
        "/api/v1/official-exam-documents",
        data={"exam_id": str(exam.id), "document_type": "question_paper"},
        files=_upload_files(),
        headers=headers,
    )
    document_id = created.json()["id"]

    delete_response = await client.delete(
        f"/api/v1/official-exam-documents/{document_id}", headers=headers
    )
    assert delete_response.status_code == 204

    get_after_delete = await client.get(
        f"/api/v1/official-exam-documents/{document_id}", headers=headers
    )
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/official-exam-documents/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == document_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/official-exam-documents/{document_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(
        f"/api/v1/official-exam-documents/{document_id}", headers=headers
    )
    assert get_after_restore.status_code == 200


async def test_official_exam_document_cancel_then_retry_workflow(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedadmin11", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="CANCELRETRY")
    token = await _login(client, "oedadmin11")
    headers = _institution_headers(token, exam.institution_id)

    created = await client.post(
        "/api/v1/official-exam-documents",
        data={"exam_id": str(exam.id), "document_type": "question_paper"},
        files=_upload_files(),
        headers=headers,
    )
    document_id = created.json()["id"]

    cancel_response = await client.post(
        f"/api/v1/official-exam-documents/{document_id}/cancel", headers=headers
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["ocr_status"] == "cancelled"

    retry_response = await client.post(
        f"/api/v1/official-exam-documents/{document_id}/retry", headers=headers
    )
    assert retry_response.status_code == 200
    assert retry_response.json()["ocr_status"] == "stored"


async def test_official_exam_document_cancel_rejects_already_completed(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedadmin12", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="NOCANCEL")
    token = await _login(client, "oedadmin12")
    headers = _institution_headers(token, exam.institution_id)

    created = await client.post(
        "/api/v1/official-exam-documents",
        data={"exam_id": str(exam.id), "document_type": "question_paper"},
        files=_upload_files(),
        headers=headers,
    )
    document_id = created.json()["id"]

    first_cancel = await client.post(
        f"/api/v1/official-exam-documents/{document_id}/cancel", headers=headers
    )
    assert first_cancel.status_code == 200

    second_cancel = await client.post(
        f"/api/v1/official-exam-documents/{document_id}/cancel", headers=headers
    )
    assert second_cancel.status_code == 409


async def test_list_official_exam_documents_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedadmin13", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="LISTENV")
    token = await _login(client, "oedadmin13")
    headers = _institution_headers(token, exam.institution_id)

    for i in range(5):
        response = await client.post(
            "/api/v1/official-exam-documents",
            data={"exam_id": str(exam.id), "document_type": "question_paper"},
            files=_upload_files(filename=f"qp{i}.pdf", content=f"content {i}".encode()),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get(
        "/api/v1/official-exam-documents?page=1&page_size=2", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3
