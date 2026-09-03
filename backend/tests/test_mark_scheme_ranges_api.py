"""MarkSchemeRange API tests: read/update/verify, tenancy, and the
`/expand` endpoint's mark-scheme expansion against a realistic
multi-range document."""

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
from app.models.mark_scheme_range import MarkSchemeRange
from app.models.official_exam_document import OfficialExamDocument
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


async def _create_document(db_session: AsyncSession, *, code: str) -> OfficialExamDocument:
    """Builds the full Institution->...->Exam->OfficialExamDocument parent
    chain (mirroring `tests/test_answer_scripts_api.py`'s
    `_create_exam_session` helper, but stopping at `OfficialExamDocument`
    instead of `ExamSession`/`AnswerScript`)."""
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

    uploader = await create_test_user(db_session, username=f"uploader_{code.lower()}")
    document = OfficialExamDocument(
        institution_id=institution.id,
        exam_id=exam.id,
        uploaded_by=uploader.id,
        document_type="mark_scheme",
        original_filename=f"mark-scheme-{code}.pdf",
        mime_type="application/pdf",
    )
    db_session.add(document)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(document)
    return document


async def _create_range(
    db_session: AsyncSession, document: OfficialExamDocument, *, overrides: dict[str, object]
) -> MarkSchemeRange:
    defaults: dict[str, object] = {
        "institution_id": document.institution_id,
        "document_id": document.id,
        "question_range_start": "1",
        "question_range_end": "5",
        "marks_per_question": Decimal("1.00"),
        "display_order": 0,
    }
    defaults.update(overrides)
    scheme_range = MarkSchemeRange(**defaults)  # type: ignore[arg-type]
    db_session.add(scheme_range)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(scheme_range)
    return scheme_range


async def test_get_nonexistent_mark_scheme_range_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="msradmin1", role=seed_rbac["super_admin"])
    document = await _create_document(db_session, code="404")
    token = await _login(client, "msradmin1")

    response = await client.get(
        f"/api/v1/mark-scheme-ranges/{uuid.uuid4()}",
        headers=_institution_headers(token, document.institution_id),
    )

    assert response.status_code == 404


async def test_list_mark_scheme_ranges_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="msradmin2", role=seed_rbac["super_admin"])
    document = await _create_document(db_session, code="NOHEADER")
    await _create_range(db_session, document, overrides={})
    token = await _login(client, "msradmin2")

    response = await client.get("/api/v1/mark-scheme-ranges", headers=auth_headers(token))

    assert response.status_code == 422


async def test_non_privileged_role_cannot_read_mark_scheme_ranges(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="msrstudent1", role=seed_rbac["student"])
    document = await _create_document(db_session, code="FORBIDDEN")
    token = await _login(client, "msrstudent1")

    response = await client.get(
        "/api/v1/mark-scheme-ranges", headers=_institution_headers(token, document.institution_id)
    )

    assert response.status_code == 403


async def test_non_privileged_role_cannot_update_mark_scheme_range(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="msrstudent2", role=seed_rbac["student"])
    document = await _create_document(db_session, code="FORBIDDEN2")
    scheme_range = await _create_range(db_session, document, overrides={})
    token = await _login(client, "msrstudent2")

    response = await client.patch(
        f"/api/v1/mark-scheme-ranges/{scheme_range.id}",
        json={"marks_per_question": "2.00"},
        headers=_institution_headers(token, document.institution_id),
    )

    assert response.status_code == 403


async def test_mark_scheme_range_list_filters_by_document_id(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="msradmin3", role=seed_rbac["super_admin"])
    document_a = await _create_document(db_session, code="DOCA")
    document_b = await _create_document(db_session, code="DOCB")
    range_a = await _create_range(
        db_session, document_a, overrides={"question_range_start": "1", "question_range_end": "5"}
    )
    await _create_range(
        db_session, document_b, overrides={"question_range_start": "1", "question_range_end": "5"}
    )
    token = await _login(client, "msradmin3")

    response = await client.get(
        f"/api/v1/mark-scheme-ranges?document_id={document_a.id}",
        headers=_institution_headers(token, document_a.institution_id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(range_a.id)


async def test_list_mark_scheme_ranges_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="msradmin4", role=seed_rbac["super_admin"])
    document = await _create_document(db_session, code="LISTENV")
    for i in range(5):
        await _create_range(
            db_session,
            document,
            overrides={
                "question_range_start": str(i * 5 + 1),
                "question_range_end": str(i * 5 + 5),
                "display_order": i,
            },
        )
    token = await _login(client, "msradmin4")
    headers = _institution_headers(token, document.institution_id)

    response = await client.get("/api/v1/mark-scheme-ranges?page=1&page_size=2", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_mark_scheme_range_update_and_verify_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="msradmin5", role=seed_rbac["super_admin"])
    document = await _create_document(db_session, code="ROUNDTRIP")
    scheme_range = await _create_range(db_session, document, overrides={})
    token = await _login(client, "msradmin5")
    headers = _institution_headers(token, document.institution_id)

    get_response = await client.get(
        f"/api/v1/mark-scheme-ranges/{scheme_range.id}", headers=headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["verification_status"] == "pending"
    assert get_response.json()["verified_by"] is None

    update_response = await client.patch(
        f"/api/v1/mark-scheme-ranges/{scheme_range.id}",
        json={
            "question_range_start": "1",
            "question_range_end": "10",
            "marks_per_question": "2.50",
        },
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert updated_body["question_range_end"] == "10"
    assert updated_body["marks_per_question"] == "2.50"

    verify_response = await client.post(
        f"/api/v1/mark-scheme-ranges/{scheme_range.id}/verify", headers=headers
    )
    assert verify_response.status_code == 200
    verified_body = verify_response.json()
    assert verified_body["verification_status"] == "verified"
    assert verified_body["verified_by"] is not None
    assert verified_body["verified_at"] is not None


async def test_expand_mark_scheme_ranges_endpoint(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """The brief's own example: "Questions 1-12 = 1 mark",
    "Questions 13-17 = 2 marks", "Questions 18-25 = 14 marks"."""
    await create_test_user(db_session, username="msradmin6", role=seed_rbac["super_admin"])
    document = await _create_document(db_session, code="EXPAND")
    await _create_range(
        db_session,
        document,
        overrides={
            "question_range_start": "1",
            "question_range_end": "12",
            "marks_per_question": Decimal("1.00"),
            "display_order": 0,
        },
    )
    await _create_range(
        db_session,
        document,
        overrides={
            "question_range_start": "13",
            "question_range_end": "17",
            "marks_per_question": Decimal("2.00"),
            "display_order": 1,
        },
    )
    await _create_range(
        db_session,
        document,
        overrides={
            "question_range_start": "18",
            "question_range_end": "25",
            "marks_per_question": Decimal("14.00"),
            "display_order": 2,
        },
    )
    token = await _login(client, "msradmin6")
    headers = _institution_headers(token, document.institution_id)

    response = await client.get(
        f"/api/v1/mark-scheme-ranges/expand?document_id={document.id}", headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    marks_by_question = body["marks_by_question"]
    assert len(marks_by_question) == 25
    assert marks_by_question["1"] == "1.00"
    assert marks_by_question["12"] == "1.00"
    assert marks_by_question["13"] == "2.00"
    assert marks_by_question["17"] == "2.00"
    assert marks_by_question["18"] == "14.00"
    assert marks_by_question["25"] == "14.00"
    assert body["warnings"] == []


async def test_expand_mark_scheme_ranges_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="msradmin7", role=seed_rbac["super_admin"])
    document = await _create_document(db_session, code="EXPANDNOHEADER")
    await _create_range(db_session, document, overrides={})
    token = await _login(client, "msradmin7")

    response = await client.get(
        f"/api/v1/mark-scheme-ranges/expand?document_id={document.id}", headers=auth_headers(token)
    )

    assert response.status_code == 422
