"""
OCR output hierarchy API tests (`OCRResult`/`OCRBlock`/`OCRLine`/`OCRWord`).

All four entities are read-only from the API's perspective, so
`create_with_hierarchy()` (the one real write path, called directly by
pipeline/task code, never through a route) is exercised against the
service directly rather than via HTTP -- mirroring this module's other
"real service method, no route" entities. `GET` endpoints are then tested
against rows seeded through that same service call.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.models.answer_script import AnswerScript
from app.models.answer_script_page import AnswerScriptPage
from app.models.assessment import Assessment
from app.models.assessment_status import AssessmentStatus
from app.models.assessment_type import AssessmentType
from app.models.audit_log import AuditLog
from app.models.batch import Batch
from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.exam import Exam
from app.models.exam_session import ExamSession
from app.models.institution import Institution
from app.models.ocr_block import OCRBlock
from app.models.ocr_job import OCRJob
from app.models.ocr_line import OCRLine
from app.models.ocr_provider import OCRProvider
from app.models.ocr_word import OCRWord
from app.models.program import Program
from app.models.section import Section
from app.models.subject import Subject
from app.models.subject_category import SubjectCategory
from app.services.ocr.base import (
    BoundingBox,
    OCRBlockResult,
    OCRLineResult,
    OCRPageResult,
    OCRWordResult,
)
from app.services.ocr_result_service import OCRResultService
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
    (mirroring `test_ocr_jobs_api.py`'s `_create_answer_script` helper)
    plus an uploader `User` and a persisted `AnswerScript`."""
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


async def _create_page(
    db_session: AsyncSession, answer_script: AnswerScript, *, page_number: int = 1
) -> AnswerScriptPage:
    page = AnswerScriptPage(
        institution_id=answer_script.institution_id,
        answer_script_id=answer_script.id,
        page_number=page_number,
        status="preprocessed",
    )
    db_session.add(page)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(page)
    return page


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


async def _create_job(
    db_session: AsyncSession, answer_script: AnswerScript, provider: OCRProvider
) -> OCRJob:
    job = OCRJob(
        institution_id=answer_script.institution_id,
        answer_script_id=answer_script.id,
        ocr_provider_id=provider.id,
        status="running",
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(job)
    return job


def _build_page_result(*, raw_text: str = "Hello World") -> OCRPageResult:
    """One block, one line, two words -- enough shape to exercise every
    level of the `OCRResult 1-* OCRBlock 1-* OCRLine 1-* OCRWord` tree."""
    word_1 = OCRWordResult(
        text="Hello", bounding_box=BoundingBox(10, 10, 50, 20), confidence=91.5, reading_order=0
    )
    word_2 = OCRWordResult(
        text="World", bounding_box=BoundingBox(65, 10, 50, 20), confidence=88.25, reading_order=1
    )
    line = OCRLineResult(
        text=raw_text,
        bounding_box=BoundingBox(10, 10, 105, 20),
        confidence=90.0,
        reading_order=0,
        words=[word_1, word_2],
    )
    block = OCRBlockResult(
        bounding_box=BoundingBox(5, 5, 120, 30),
        confidence=89.0,
        reading_order=0,
        block_type="text",
        lines=[line],
    )
    return OCRPageResult(
        raw_text=raw_text,
        average_confidence=89.75,
        language="eng",
        rotation_degrees=0.5,
        blocks=[block],
    )


# --- create_with_hierarchy (service, not exposed via any route) --------


async def test_create_with_hierarchy_persists_full_tree_and_logs_audit(
    db_session: AsyncSession, seed_rbac
) -> None:
    user = await create_test_user(db_session, username="ocrsvc1", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="HIER")
    page = await _create_page(db_session, script)
    provider = await _create_provider(db_session, code="tesseract_h1")
    job = await _create_job(db_session, script, provider)

    service = OCRResultService(db_session)
    result = await service.create_with_hierarchy(
        script.institution_id, page.id, job.id, _build_page_result(), created_by=user.id
    )
    await db_session.commit()

    assert result.id is not None
    assert result.answer_script_page_id == page.id
    assert result.ocr_job_id == job.id
    assert result.raw_text == "Hello World"
    assert result.normalized_text is None
    assert result.average_confidence == Decimal("89.75")
    assert result.rotation_degrees == Decimal("0.5")
    assert result.reading_order_verified is False

    blocks = (
        (await db_session.execute(select(OCRBlock).where(OCRBlock.ocr_result_id == result.id)))
        .scalars()
        .all()
    )
    assert len(blocks) == 1
    assert blocks[0].block_type == "text"
    assert blocks[0].institution_id == script.institution_id

    lines = (
        (await db_session.execute(select(OCRLine).where(OCRLine.ocr_block_id == blocks[0].id)))
        .scalars()
        .all()
    )
    assert len(lines) == 1
    assert lines[0].text == "Hello World"

    words = (
        (await db_session.execute(select(OCRWord).where(OCRWord.ocr_line_id == lines[0].id)))
        .scalars()
        .all()
    )
    assert {w.text for w in words} == {"Hello", "World"}
    assert all(w.institution_id == script.institution_id for w in words)

    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.resource_id == str(result.id),
                    AuditLog.action == AuditAction.OCR_PROCESSING_COMPLETED,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1


async def test_create_with_hierarchy_enforces_one_result_per_page(
    db_session: AsyncSession, seed_rbac
) -> None:
    """`OCRResult.answer_script_page_id` is unique -- a page can only ever
    have one OCR result."""
    user = await create_test_user(db_session, username="ocrsvc2", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="DUPPAGE")
    page = await _create_page(db_session, script)
    provider = await _create_provider(db_session, code="tesseract_h2")
    job = await _create_job(db_session, script, provider)

    service = OCRResultService(db_session)
    await service.create_with_hierarchy(
        script.institution_id, page.id, job.id, _build_page_result(), created_by=user.id
    )
    await db_session.commit()

    with pytest.raises(IntegrityError):
        await service.create_with_hierarchy(
            script.institution_id, page.id, job.id, _build_page_result(), created_by=user.id
        )
    await db_session.rollback()


# --- OCRResult GET endpoints --------------------------------------------


async def test_get_ocr_result_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    user = await create_test_user(db_session, username="ocradmin1", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="NOHEADER")
    page = await _create_page(db_session, script)
    provider = await _create_provider(db_session, code="tesseract_r1")
    job = await _create_job(db_session, script, provider)
    result = await OCRResultService(db_session).create_with_hierarchy(
        script.institution_id, page.id, job.id, _build_page_result(), created_by=user.id
    )
    await db_session.commit()
    token = await _login(client, "ocradmin1")

    response = await client.get(f"/api/v1/ocr-results/{result.id}", headers=auth_headers(token))

    assert response.status_code == 422


async def test_non_privileged_role_cannot_list_ocr_results(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocrstudent1", role=seed_rbac["student"])
    script = await _create_answer_script(db_session, code="FORBIDDEN")
    token = await _login(client, "ocrstudent1")

    response = await client.get(
        "/api/v1/ocr-results", headers=_institution_headers(token, script.institution_id)
    )

    assert response.status_code == 403


async def test_get_nonexistent_ocr_result_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocradmin2", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="404")
    token = await _login(client, "ocradmin2")

    response = await client.get(
        f"/api/v1/ocr-results/{uuid.uuid4()}",
        headers=_institution_headers(token, script.institution_id),
    )

    assert response.status_code == 404


async def test_get_ocr_result_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    user = await create_test_user(db_session, username="ocradmin3", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="ROUNDTRIP")
    page = await _create_page(db_session, script)
    provider = await _create_provider(db_session, code="tesseract_r3")
    job = await _create_job(db_session, script, provider)
    result = await OCRResultService(db_session).create_with_hierarchy(
        script.institution_id, page.id, job.id, _build_page_result(), created_by=user.id
    )
    await db_session.commit()
    token = await _login(client, "ocradmin3")

    response = await client.get(
        f"/api/v1/ocr-results/{result.id}",
        headers=_institution_headers(token, script.institution_id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(result.id)
    assert body["answer_script_page_id"] == str(page.id)
    assert body["ocr_job_id"] == str(job.id)
    assert body["raw_text"] == "Hello World"
    assert body["normalized_text"] is None
    assert Decimal(body["average_confidence"]) == Decimal("89.75")
    assert Decimal(body["rotation_degrees"]) == Decimal("0.5")
    assert body["reading_order_verified"] is False


async def test_list_ocr_results_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    user = await create_test_user(db_session, username="ocradmin4", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="LISTENV")
    provider = await _create_provider(db_session, code="tesseract_r4")
    job = await _create_job(db_session, script, provider)

    service = OCRResultService(db_session)
    for i in range(5):
        page = await _create_page(db_session, script, page_number=i + 1)
        await service.create_with_hierarchy(
            script.institution_id,
            page.id,
            job.id,
            _build_page_result(raw_text=f"Page {i}"),
            created_by=user.id,
        )
        await db_session.commit()

    token = await _login(client, "ocradmin4")
    headers = _institution_headers(token, script.institution_id)

    response = await client.get("/api/v1/ocr-results?page=1&page_size=2", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


# --- OCRBlock / OCRLine / OCRWord GET endpoints -------------------------


async def test_get_ocr_block_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    user = await create_test_user(db_session, username="ocradmin5", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="BLOCKRT")
    page = await _create_page(db_session, script)
    provider = await _create_provider(db_session, code="tesseract_b1")
    job = await _create_job(db_session, script, provider)
    result = await OCRResultService(db_session).create_with_hierarchy(
        script.institution_id, page.id, job.id, _build_page_result(), created_by=user.id
    )
    await db_session.commit()
    block = (
        await db_session.execute(select(OCRBlock).where(OCRBlock.ocr_result_id == result.id))
    ).scalar_one()

    token = await _login(client, "ocradmin5")
    headers = _institution_headers(token, script.institution_id)

    get_response = await client.get(f"/api/v1/ocr-blocks/{block.id}", headers=headers)
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["id"] == str(block.id)
    assert body["ocr_result_id"] == str(result.id)
    assert body["block_type"] == "text"

    list_response = await client.get("/api/v1/ocr-blocks", headers=headers)
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert set(list_body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert list_body["total"] == 1


async def test_get_ocr_line_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    user = await create_test_user(db_session, username="ocradmin6", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="LINERT")
    page = await _create_page(db_session, script)
    provider = await _create_provider(db_session, code="tesseract_l1")
    job = await _create_job(db_session, script, provider)
    result = await OCRResultService(db_session).create_with_hierarchy(
        script.institution_id, page.id, job.id, _build_page_result(), created_by=user.id
    )
    await db_session.commit()
    block = (
        await db_session.execute(select(OCRBlock).where(OCRBlock.ocr_result_id == result.id))
    ).scalar_one()
    line = (
        await db_session.execute(select(OCRLine).where(OCRLine.ocr_block_id == block.id))
    ).scalar_one()

    token = await _login(client, "ocradmin6")
    headers = _institution_headers(token, script.institution_id)

    response = await client.get(f"/api/v1/ocr-lines/{line.id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(line.id)
    assert body["ocr_block_id"] == str(block.id)
    assert body["text"] == "Hello World"


async def test_get_ocr_word_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    user = await create_test_user(db_session, username="ocradmin7", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="WORDRT")
    page = await _create_page(db_session, script)
    provider = await _create_provider(db_session, code="tesseract_w1")
    job = await _create_job(db_session, script, provider)
    result = await OCRResultService(db_session).create_with_hierarchy(
        script.institution_id, page.id, job.id, _build_page_result(), created_by=user.id
    )
    await db_session.commit()
    block = (
        await db_session.execute(select(OCRBlock).where(OCRBlock.ocr_result_id == result.id))
    ).scalar_one()
    line = (
        await db_session.execute(select(OCRLine).where(OCRLine.ocr_block_id == block.id))
    ).scalar_one()
    word = (
        await db_session.execute(
            select(OCRWord).where(OCRWord.ocr_line_id == line.id, OCRWord.text == "Hello")
        )
    ).scalar_one()

    token = await _login(client, "ocradmin7")
    headers = _institution_headers(token, script.institution_id)

    response = await client.get(f"/api/v1/ocr-words/{word.id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(word.id)
    assert body["ocr_line_id"] == str(line.id)
    assert body["text"] == "Hello"
    assert Decimal(body["confidence"]) == Decimal("91.5")


# --- Nested tree convenience route --------------------------------------


async def test_get_ocr_result_blocks_returns_nested_tree(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    user = await create_test_user(db_session, username="ocradmin8", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="TREE")
    page = await _create_page(db_session, script)
    provider = await _create_provider(db_session, code="tesseract_t1")
    job = await _create_job(db_session, script, provider)
    result = await OCRResultService(db_session).create_with_hierarchy(
        script.institution_id, page.id, job.id, _build_page_result(), created_by=user.id
    )
    await db_session.commit()

    token = await _login(client, "ocradmin8")
    headers = _institution_headers(token, script.institution_id)

    response = await client.get(f"/api/v1/ocr-results/{result.id}/blocks", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    block = body[0]
    assert block["ocr_result_id"] == str(result.id)
    assert block["block_type"] == "text"
    assert len(block["lines"]) == 1
    line = block["lines"][0]
    assert line["text"] == "Hello World"
    assert len(line["words"]) == 2
    assert {w["text"] for w in line["words"]} == {"Hello", "World"}
    # words are ordered by `reading_order`
    assert [w["text"] for w in line["words"]] == ["Hello", "World"]


async def test_get_ocr_result_blocks_returns_404_for_nonexistent_result(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocradmin9", role=seed_rbac["super_admin"])
    script = await _create_answer_script(db_session, code="TREE404")
    token = await _login(client, "ocradmin9")

    response = await client.get(
        f"/api/v1/ocr-results/{uuid.uuid4()}/blocks",
        headers=_institution_headers(token, script.institution_id),
    )

    assert response.status_code == 404
