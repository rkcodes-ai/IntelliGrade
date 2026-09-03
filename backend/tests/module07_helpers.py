"""Shared fixture-building helpers for Module 07 tests.

Extends `tests.test_official_exam_documents_api._create_exam`'s
Institution->...->Exam chain with the additional pieces Module 07 needs
that Module 06 didn't: `AssessmentConfiguration` (pass/fail threshold),
`StudentEnrollment` (batch-scoped finalization + roll-number search), and
directly-constructed `AnswerEvaluation` rows with `final_marks` already
set (bypassing the real AI provider call — the AI computation itself is
already covered by Module 06's tests; these fixtures are for exercising
Module 07's own new state-machine/aggregation logic).
"""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic_status import AcademicStatus
from app.models.academic_year import AcademicYear
from app.models.ai_provider import AIProvider
from app.models.answer_evaluation import AnswerEvaluation
from app.models.answer_script import AnswerScript
from app.models.assessment import Assessment
from app.models.assessment_configuration import AssessmentConfiguration
from app.models.batch import Batch
from app.models.exam import Exam
from app.models.exam_session import ExamSession
from app.models.extracted_model_answer import ExtractedModelAnswer
from app.models.extracted_question import ExtractedQuestion
from app.models.official_exam_document import OfficialExamDocument
from app.models.section import Section
from app.models.semester import Semester
from app.models.student_enrollment import StudentEnrollment
from app.models.user_institution import UserInstitution
from tests.test_official_exam_documents_api import _create_exam


@dataclass
class ExamHierarchy:
    exam: Exam
    assessment: Assessment
    assessment_configuration: AssessmentConfiguration
    batch: Batch
    section: Section


async def create_exam_hierarchy(
    db_session: AsyncSession,
    *,
    code: str,
    maximum_marks: Decimal = Decimal("20.00"),
    passing_marks: Decimal = Decimal("8.00"),
) -> ExamHierarchy:
    exam = await _create_exam(db_session, code=code)
    assessment = await db_session.get(Assessment, exam.assessment_id)
    section = await db_session.get(Section, exam.section_id)
    batch = await db_session.get(Batch, section.batch_id)

    configuration = AssessmentConfiguration(
        institution_id=exam.institution_id,
        assessment_id=assessment.id,
        maximum_marks=maximum_marks,
        passing_marks=passing_marks,
    )
    db_session.add(configuration)
    await db_session.commit()
    await db_session.refresh(configuration)
    return ExamHierarchy(
        exam=exam,
        assessment=assessment,
        assessment_configuration=configuration,
        batch=batch,
        section=section,
    )


async def enroll_student(
    db_session: AsyncSession,
    hierarchy: ExamHierarchy,
    *,
    student_user_id: uuid.UUID,
    roll_number: str,
) -> StudentEnrollment:
    institution_id = hierarchy.exam.institution_id

    db_session.add(UserInstitution(user_id=student_user_id, institution_id=institution_id))
    await db_session.flush()

    academic_year = AcademicYear(
        institution_id=institution_id,
        year_label=f"AY-{roll_number}",
        start_date=date(2026, 6, 1),
        end_date=date(2027, 5, 31),
    )
    db_session.add(academic_year)
    await db_session.flush()

    semester = Semester(
        institution_id=institution_id,
        academic_year_id=academic_year.id,
        name=f"Sem-{roll_number}",
        semester_number=1,
        term_type="odd",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 11, 30),
    )
    db_session.add(semester)
    await db_session.flush()

    academic_status = AcademicStatus(
        institution_id=institution_id, code=f"ST-{roll_number}", name=f"Status {roll_number}"
    )
    db_session.add(academic_status)
    await db_session.flush()

    enrollment = StudentEnrollment(
        institution_id=institution_id,
        student_user_id=student_user_id,
        batch_id=hierarchy.batch.id,
        section_id=hierarchy.section.id,
        course_id=hierarchy.batch.course_id,
        academic_year_id=academic_year.id,
        semester_id=semester.id,
        academic_status_id=academic_status.id,
        roll_number=roll_number,
        enrollment_date=date(2026, 6, 1),
    )
    db_session.add(enrollment)
    await db_session.commit()
    await db_session.refresh(enrollment)
    return enrollment


async def seed_ai_provider(db_session: AsyncSession) -> AIProvider:
    """Idempotent — tests that build more than one exam hierarchy in the
    same session (e.g. to compare two institutions/exams) may call this
    more than once."""
    from sqlalchemy import select

    existing = (
        (await db_session.execute(select(AIProvider).where(AIProvider.code == "lexical_heuristic")))
        .scalars()
        .first()
    )
    if existing is not None:
        return existing

    provider = AIProvider(
        code="lexical_heuristic",
        name="Lexical Heuristic",
        is_enabled=True,
        is_implemented=True,
        is_default=True,
    )
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)
    return provider


async def create_finalizable_exam_session(
    db_session: AsyncSession,
    hierarchy: ExamHierarchy,
    *,
    student_user_id: uuid.UUID,
    uploader_id: uuid.UUID,
    ai_provider_id: uuid.UUID,
    question_marks: list[tuple[Decimal, Decimal]],
    code: str,
) -> ExamSession:
    """Creates one `ExamSession` with `len(question_marks)` extracted
    questions, each already evaluated with `(final_marks, max_marks)`
    directly set — ready for `ExamResultService.finalize_student`."""
    institution_id = hierarchy.exam.institution_id

    exam_session = ExamSession(
        institution_id=institution_id, exam_id=hierarchy.exam.id, student_user_id=student_user_id
    )
    db_session.add(exam_session)
    await db_session.flush()

    qp_document = OfficialExamDocument(
        institution_id=institution_id,
        exam_id=hierarchy.exam.id,
        uploaded_by=uploader_id,
        document_type="question_paper",
        original_filename=f"{code}-qp.pdf",
        mime_type="application/pdf",
        file_size_bytes=10,
        ocr_status="completed",
    )
    db_session.add(qp_document)
    await db_session.flush()

    answer_script = AnswerScript(
        institution_id=institution_id,
        exam_session_id=exam_session.id,
        uploaded_by=uploader_id,
        original_filename=f"{code}-script.pdf",
        mime_type="application/pdf",
        file_size_bytes=10,
        checksum_sha256=str(uuid.uuid4()).replace("-", "") * 2,
        status="completed",
        structured_content={"schema_version": 1, "page_count": 1, "pages": []},
    )
    db_session.add(answer_script)
    await db_session.flush()

    for index, (final_marks, max_marks) in enumerate(question_marks, start=1):
        question = ExtractedQuestion(
            institution_id=institution_id,
            document_id=qp_document.id,
            question_number=str(index),
            question_text=f"Question {index} for {code}",
            raw_ocr_text=f"Question {index}",
            final_marks=max_marks,
            display_order=index - 1,
        )
        db_session.add(question)
        await db_session.flush()

        evaluation = AnswerEvaluation(
            institution_id=institution_id,
            exam_session_id=exam_session.id,
            answer_script_id=answer_script.id,
            extracted_question_id=question.id,
            ai_provider_id=ai_provider_id,
            max_marks=max_marks,
            suggested_marks=final_marks,
            final_marks=final_marks,
            review_status="teacher_confirmed",
            confidence_score=Decimal("95.00"),
            confidence_tier="high",
        )
        db_session.add(evaluation)

    await db_session.commit()
    await db_session.refresh(exam_session)
    return exam_session


async def create_model_answer(
    db_session: AsyncSession, hierarchy: ExamHierarchy, *, uploader_id: uuid.UUID, code: str
) -> ExtractedModelAnswer:
    ma_document = OfficialExamDocument(
        institution_id=hierarchy.exam.institution_id,
        exam_id=hierarchy.exam.id,
        uploaded_by=uploader_id,
        document_type="model_answer",
        original_filename=f"{code}-ma.pdf",
        mime_type="application/pdf",
        file_size_bytes=10,
        ocr_status="completed",
    )
    db_session.add(ma_document)
    await db_session.flush()
    model_answer = ExtractedModelAnswer(
        institution_id=hierarchy.exam.institution_id,
        document_id=ma_document.id,
        question_number="1",
        answer_text=f"Model answer for {code}",
        raw_ocr_text=f"Model answer for {code}",
        display_order=0,
    )
    db_session.add(model_answer)
    await db_session.commit()
    await db_session.refresh(model_answer)
    return model_answer
