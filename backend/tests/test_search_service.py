"""Tests for `SearchService` (Module 07, Feature 9)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.search_service import SearchService
from tests.conftest import create_test_user
from tests.module07_helpers import create_exam_hierarchy, enroll_student


async def test_search_finds_student_by_name_and_roll_number(
    db_session: AsyncSession, seed_rbac
) -> None:
    hierarchy = await create_exam_hierarchy(db_session, code="SEARCHSTU")
    student = await create_test_user(
        db_session,
        username="search_student1",
        full_name="Priya Sharma",
        role=seed_rbac["student"],
    )
    await enroll_student(
        db_session, hierarchy, student_user_id=student.id, roll_number="ROLL-SEARCH-01"
    )

    service = SearchService(db_session)

    by_name = await service.search(hierarchy.exam.institution_id, "Priya")
    assert any(r.type == "student" and r.id == student.id for r in by_name)

    by_roll = await service.search(hierarchy.exam.institution_id, "ROLL-SEARCH-01")
    assert any(r.type == "student" and r.id == student.id for r in by_roll)


async def test_search_finds_subject_by_name(db_session: AsyncSession) -> None:
    hierarchy = await create_exam_hierarchy(db_session, code="SEARCHSUB")
    from app.models.assessment import Assessment
    from app.models.subject import Subject

    assessment = await db_session.get(Assessment, hierarchy.assessment.id)
    subject = await db_session.get(Subject, assessment.subject_id)

    service = SearchService(db_session)
    results = await service.search(hierarchy.exam.institution_id, subject.name)
    assert any(r.type == "subject" and r.id == subject.id for r in results)


async def test_search_finds_question_by_text(db_session: AsyncSession) -> None:
    hierarchy = await create_exam_hierarchy(db_session, code="SEARCHQ")
    uploader = await create_test_user(db_session, username="search_uploader_q")
    from app.models.extracted_question import ExtractedQuestion
    from app.models.official_exam_document import OfficialExamDocument

    document = OfficialExamDocument(
        institution_id=hierarchy.exam.institution_id,
        exam_id=hierarchy.exam.id,
        uploaded_by=uploader.id,
        document_type="question_paper",
        original_filename="qp.pdf",
        mime_type="application/pdf",
        file_size_bytes=10,
        ocr_status="completed",
    )
    db_session.add(document)
    await db_session.flush()
    question = ExtractedQuestion(
        institution_id=hierarchy.exam.institution_id,
        document_id=document.id,
        question_number="1",
        question_text="Explain quantum entanglement in simple terms.",
        raw_ocr_text="Explain quantum entanglement in simple terms.",
        display_order=0,
    )
    db_session.add(question)
    await db_session.commit()

    service = SearchService(db_session)
    results = await service.search(hierarchy.exam.institution_id, "quantum entanglement")
    assert any(r.type == "question" and r.id == question.id for r in results)


async def test_search_scoped_to_institution(db_session: AsyncSession, seed_rbac) -> None:
    hierarchy_a = await create_exam_hierarchy(db_session, code="SEARCHISOA")
    hierarchy_b = await create_exam_hierarchy(db_session, code="SEARCHISOB")
    student = await create_test_user(
        db_session,
        username="search_iso_student",
        full_name="Isolation Test Student",
        role=seed_rbac["student"],
    )
    await enroll_student(db_session, hierarchy_a, student_user_id=student.id, roll_number="ISO-01")

    service = SearchService(db_session)
    results_in_b = await service.search(hierarchy_b.exam.institution_id, "Isolation Test Student")
    assert results_in_b == []
