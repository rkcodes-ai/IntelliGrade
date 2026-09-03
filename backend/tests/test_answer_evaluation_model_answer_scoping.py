"""Regression tests for the Model Answer scoping fix in
`AnswerEvaluationService.evaluate_question()` (Module 06 correctness
milestone, see the repository audit).

**The bug this file guards against:** the previous version resolved the
model answer for a question by `institution_id + question_number` alone —
a plain string match with no scoping to the actual exam/document the
question came from. Any two exams (even two exams for two different
subjects) that happened to both number a question "1" could silently
attach the wrong exam's model answer to an evaluation.

**The fix:** the model answer is now resolved via the real, pre-existing
relationship chain `ExamSession.exam_id == OfficialExamDocument.exam_id`
(the same `Exam` the evaluated question's own document belongs to), and
only an `ExtractedModelAnswer` whose `document_id` points at THAT exam's
`document_type="model_answer"` document may ever be selected. No new
table or column was introduced — this reuses the existing FKs.

Every test below builds two (or more) full, independent exam/question/
model-answer chains sharing the same `question_number`, then proves the
service picks only the model answer that actually belongs to the exam
being evaluated — never the other one.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_provider import AIProvider
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
from app.models.extracted_model_answer import ExtractedModelAnswer
from app.models.extracted_question import ExtractedQuestion
from app.models.institution import Institution
from app.models.official_exam_document import OfficialExamDocument
from app.models.program import Program
from app.models.section import Section
from app.models.subject import Subject
from app.models.subject_category import SubjectCategory
from app.models.user import User
from tests.conftest import auth_headers, create_test_user
from tests.test_official_exam_documents_api import _login

_QUESTION_TEXT = "Explain the process of photosynthesis in plants."


def _institution_headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


async def _create_institution(db_session: AsyncSession, *, code: str) -> Institution:
    institution = Institution(
        name=f"Institution {code}", code=f"I-{code}", institution_type="university", is_active=True
    )
    db_session.add(institution)
    await db_session.flush()
    return institution


async def _create_exam_under(
    db_session: AsyncSession, institution: Institution, *, code: str
) -> Exam:
    """Builds Campus->Department->Program->Course->Subject->Assessment->Exam
    under an EXISTING institution — distinct from
    `test_official_exam_documents_api._create_exam`, which always creates a
    brand-new institution per call. Reusing the same institution here is
    what lets these tests prove same-tenant, cross-exam isolation (the
    actual bug), not just cross-tenant isolation (which the pre-existing
    `institution_id` filter already handled correctly)."""
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
    return exam


async def _seed_question_and_model_answer(
    db_session: AsyncSession,
    *,
    exam: Exam,
    uploader: User,
    question_number: str = "1",
    model_answer_text: str,
    model_answer_document_kwargs: dict | None = None,
) -> tuple[ExtractedQuestion, ExtractedModelAnswer, OfficialExamDocument]:
    qp_document = OfficialExamDocument(
        institution_id=exam.institution_id,
        exam_id=exam.id,
        uploaded_by=uploader.id,
        document_type="question_paper",
        original_filename="qp.pdf",
        mime_type="application/pdf",
        file_size_bytes=10,
        ocr_status="completed",
    )
    ma_document_kwargs = {
        "institution_id": exam.institution_id,
        "exam_id": exam.id,
        "uploaded_by": uploader.id,
        "document_type": "model_answer",
        "original_filename": "ma.pdf",
        "mime_type": "application/pdf",
        "file_size_bytes": 10,
        "ocr_status": "completed",
        **(model_answer_document_kwargs or {}),
    }
    ma_document = OfficialExamDocument(**ma_document_kwargs)
    db_session.add_all([qp_document, ma_document])
    await db_session.flush()

    question = ExtractedQuestion(
        institution_id=exam.institution_id,
        document_id=qp_document.id,
        question_number=question_number,
        question_text=_QUESTION_TEXT,
        raw_ocr_text=_QUESTION_TEXT,
        final_marks=Decimal("10.00"),
        display_order=0,
    )
    model_answer = ExtractedModelAnswer(
        institution_id=exam.institution_id,
        document_id=ma_document.id,
        question_number=question_number,
        answer_text=model_answer_text,
        raw_ocr_text=model_answer_text,
        display_order=0,
    )
    db_session.add_all([question, model_answer])
    await db_session.flush()
    return question, model_answer, ma_document


async def _seed_exam_session_and_script(
    db_session: AsyncSession, *, exam: Exam, uploader: User, student: User, answer_text: str
) -> ExamSession:
    exam_session = ExamSession(
        institution_id=exam.institution_id, exam_id=exam.id, student_user_id=student.id
    )
    db_session.add(exam_session)
    await db_session.flush()

    answer_script = AnswerScript(
        institution_id=exam.institution_id,
        exam_session_id=exam_session.id,
        uploaded_by=uploader.id,
        original_filename="script.pdf",
        mime_type="application/pdf",
        file_size_bytes=10,
        checksum_sha256=uuid.uuid4().hex.ljust(64, "0"),
        status="completed",
        structured_content={
            "schema_version": 1,
            "page_count": 1,
            "pages": [
                {
                    "page_number": 1,
                    "detected_questions": [],
                    "blocks": [
                        {
                            "block_type": "text",
                            "reading_order": 0,
                            "lines": [{"text": answer_text, "reading_order": 0, "words": []}],
                        }
                    ],
                }
            ],
        },
    )
    db_session.add(answer_script)
    await db_session.flush()
    return exam_session


async def _seed_ai_provider(db_session: AsyncSession) -> AIProvider:
    provider = AIProvider(
        code="lexical_heuristic",
        name="Lexical Heuristic",
        is_enabled=True,
        is_implemented=True,
        is_default=True,
    )
    db_session.add(provider)
    await db_session.flush()
    return provider


async def test_two_exams_same_institution_same_question_number_do_not_cross_contaminate(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """A. Two exams, same question number. C. Multiple model answers exist.
    F/G. The correct one is picked for each; the wrong one is never picked."""
    await create_test_user(db_session, username="scopeteacher_a", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="SCOPEAB")
    uploader = await create_test_user(db_session, username="scopeuploader_a")
    student1 = await create_test_user(db_session, username="scopestudent_a1")
    student2 = await create_test_user(db_session, username="scopestudent_a2")

    exam1 = await _create_exam_under(db_session, institution, code="SCOPEEXAM1")
    exam2 = await _create_exam_under(db_session, institution, code="SCOPEEXAM2")

    question1, model_answer1, _ = await _seed_question_and_model_answer(
        db_session,
        exam=exam1,
        uploader=uploader,
        question_number="1",
        model_answer_text="Exam-one's correct answer about the Krebs cycle.",
    )
    question2, model_answer2, _ = await _seed_question_and_model_answer(
        db_session,
        exam=exam2,
        uploader=uploader,
        question_number="1",
        model_answer_text="Exam-two's correct answer about French Revolution causes.",
    )
    exam_session1 = await _seed_exam_session_and_script(
        db_session,
        exam=exam1,
        uploader=uploader,
        student=student1,
        answer_text="Q1) My answer about the Krebs cycle.",
    )
    exam_session2 = await _seed_exam_session_and_script(
        db_session,
        exam=exam2,
        uploader=uploader,
        student=student2,
        answer_text="Q1) My answer about French Revolution causes.",
    )
    await db_session.commit()
    await db_session.refresh(question1)
    await db_session.refresh(question2)
    await db_session.refresh(model_answer1)
    await db_session.refresh(model_answer2)
    await db_session.refresh(exam_session1)
    await db_session.refresh(exam_session2)

    token = await _login(client, "scopeteacher_a")
    headers = _institution_headers(token, institution.id)

    response1 = await client.post(
        "/api/v1/answer-evaluations",
        json={
            "exam_session_id": str(exam_session1.id),
            "extracted_question_id": str(question1.id),
        },
        headers=headers,
    )
    response2 = await client.post(
        "/api/v1/answer-evaluations",
        json={
            "exam_session_id": str(exam_session2.id),
            "extracted_question_id": str(question2.id),
        },
        headers=headers,
    )

    assert response1.status_code == 201
    assert response2.status_code == 201
    body1, body2 = response1.json(), response2.json()

    # F: the correct model answer is selected for each exam...
    assert body1["extracted_model_answer_id"] == str(model_answer1.id)
    assert body2["extracted_model_answer_id"] == str(model_answer2.id)
    # G: ...and the OTHER exam's model answer is never selected.
    assert body1["extracted_model_answer_id"] != str(model_answer2.id)
    assert body2["extracted_model_answer_id"] != str(model_answer1.id)


async def test_two_subjects_both_with_question_one_do_not_cross_contaminate(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """B. Two different subjects, each with a "Question 1" — `_create_exam_under`
    gives each exam its own fresh Subject/Assessment, so this exercises the
    same guarantee at the subject level, not just the raw exam level."""
    await create_test_user(db_session, username="scopeteacher_b", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="SCOPESUBJ")
    uploader = await create_test_user(db_session, username="scopeuploader_b")
    student2 = await create_test_user(db_session, username="scopestudent_b2")

    physics_exam = await _create_exam_under(db_session, institution, code="SCOPEPHYS")
    history_exam = await _create_exam_under(db_session, institution, code="SCOPEHIST")

    _, physics_model_answer, _ = await _seed_question_and_model_answer(
        db_session,
        exam=physics_exam,
        uploader=uploader,
        question_number="1",
        model_answer_text="Newton's second law: F = ma.",
    )
    history_question, history_model_answer, _ = await _seed_question_and_model_answer(
        db_session,
        exam=history_exam,
        uploader=uploader,
        question_number="1",
        model_answer_text="The causes of World War One included militarism and alliances.",
    )
    history_session = await _seed_exam_session_and_script(
        db_session,
        exam=history_exam,
        uploader=uploader,
        student=student2,
        answer_text="Q1) Militarism and alliances caused World War One.",
    )
    await db_session.commit()
    await db_session.refresh(history_question)
    await db_session.refresh(history_model_answer)
    await db_session.refresh(physics_model_answer)
    await db_session.refresh(history_session)

    token = await _login(client, "scopeteacher_b")
    headers = _institution_headers(token, institution.id)

    response = await client.post(
        "/api/v1/answer-evaluations",
        json={
            "exam_session_id": str(history_session.id),
            "extracted_question_id": str(history_question.id),
        },
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["extracted_model_answer_id"] == str(history_model_answer.id)
    assert body["extracted_model_answer_id"] != str(physics_model_answer.id)


async def test_multiple_tenants_same_question_number_never_cross_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """D. Two separate institutions (tenants), both with "Question 1"."""
    await create_test_user(db_session, username="scopeteacher_d1", role=seed_rbac["super_admin"])
    await create_test_user(db_session, username="scopeteacher_d2", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)

    institution_x = await _create_institution(db_session, code="SCOPETENX")
    institution_y = await _create_institution(db_session, code="SCOPETENY")
    uploader_x = await create_test_user(db_session, username="scopeuploader_x")
    uploader_y = await create_test_user(db_session, username="scopeuploader_y")
    student_x = await create_test_user(db_session, username="scopestudent_x")

    exam_x = await _create_exam_under(db_session, institution_x, code="SCOPEEXX")
    exam_y = await _create_exam_under(db_session, institution_y, code="SCOPEEXY")

    question_x, model_answer_x, _ = await _seed_question_and_model_answer(
        db_session,
        exam=exam_x,
        uploader=uploader_x,
        question_number="1",
        model_answer_text="Institution X's answer.",
    )
    _, model_answer_y, _ = await _seed_question_and_model_answer(
        db_session,
        exam=exam_y,
        uploader=uploader_y,
        question_number="1",
        model_answer_text="Institution Y's answer.",
    )
    session_x = await _seed_exam_session_and_script(
        db_session,
        exam=exam_x,
        uploader=uploader_x,
        student=student_x,
        answer_text="Q1) My answer for institution X.",
    )
    await db_session.commit()
    await db_session.refresh(question_x)
    await db_session.refresh(model_answer_x)
    await db_session.refresh(model_answer_y)
    await db_session.refresh(session_x)

    token = await _login(client, "scopeteacher_d1")
    headers = _institution_headers(token, institution_x.id)

    response = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(session_x.id), "extracted_question_id": str(question_x.id)},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["extracted_model_answer_id"] == str(model_answer_x.id)
    assert body["extracted_model_answer_id"] != str(model_answer_y.id)


async def test_multiple_exam_sessions_of_same_exam_share_the_same_correct_model_answer(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """E. Multiple exam sessions (two different students sitting the SAME
    exam) must both correctly resolve to the one shared, correct model
    answer for that exam — the scoping fix must not break legitimate
    same-exam sharing while preventing cross-exam leakage."""
    await create_test_user(db_session, username="scopeteacher_e", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="SCOPESHARE")
    uploader = await create_test_user(db_session, username="scopeuploader_e")
    student1 = await create_test_user(db_session, username="scopestudent_e1")
    student2 = await create_test_user(db_session, username="scopestudent_e2")

    exam = await _create_exam_under(db_session, institution, code="SCOPESHAREEXAM")
    question, model_answer, _ = await _seed_question_and_model_answer(
        db_session,
        exam=exam,
        uploader=uploader,
        question_number="1",
        model_answer_text="The shared correct answer for this one exam.",
    )
    session1 = await _seed_exam_session_and_script(
        db_session,
        exam=exam,
        uploader=uploader,
        student=student1,
        answer_text="Q1) The shared correct answer for this one exam.",
    )
    session2 = await _seed_exam_session_and_script(
        db_session,
        exam=exam,
        uploader=uploader,
        student=student2,
        answer_text="Q1) A slightly different phrasing of the shared answer.",
    )
    await db_session.commit()
    await db_session.refresh(question)
    await db_session.refresh(model_answer)
    await db_session.refresh(session1)
    await db_session.refresh(session2)

    token = await _login(client, "scopeteacher_e")
    headers = _institution_headers(token, institution.id)

    response1 = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(session1.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )
    response2 = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(session2.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )

    assert response1.status_code == 201
    assert response2.status_code == 201
    assert response1.json()["extracted_model_answer_id"] == str(model_answer.id)
    assert response2.json()["extracted_model_answer_id"] == str(model_answer.id)


async def test_missing_model_answer_document_evaluates_with_controlled_empty_fallback(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """H. No model_answer document has been uploaded for this exam at all —
    must not crash, and must not accidentally borrow another exam's model
    answer. `extracted_model_answer_id` must be null."""
    await create_test_user(db_session, username="scopeteacher_h", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="SCOPENOMA")
    uploader = await create_test_user(db_session, username="scopeuploader_h")
    student = await create_test_user(db_session, username="scopestudent_h")

    exam = await _create_exam_under(db_session, institution, code="SCOPENOMAEXAM")

    # Only a question_paper document — deliberately no model_answer document.
    qp_document = OfficialExamDocument(
        institution_id=exam.institution_id,
        exam_id=exam.id,
        uploaded_by=uploader.id,
        document_type="question_paper",
        original_filename="qp.pdf",
        mime_type="application/pdf",
        file_size_bytes=10,
        ocr_status="completed",
    )
    db_session.add(qp_document)
    await db_session.flush()
    question = ExtractedQuestion(
        institution_id=exam.institution_id,
        document_id=qp_document.id,
        question_number="1",
        question_text=_QUESTION_TEXT,
        raw_ocr_text=_QUESTION_TEXT,
        final_marks=Decimal("10.00"),
        display_order=0,
    )
    db_session.add(question)
    await db_session.flush()

    exam_session = await _seed_exam_session_and_script(
        db_session,
        exam=exam,
        uploader=uploader,
        student=student,
        answer_text="Q1) An answer with no model answer to compare against.",
    )
    await db_session.commit()
    await db_session.refresh(question)
    await db_session.refresh(exam_session)

    token = await _login(client, "scopeteacher_h")
    headers = _institution_headers(token, institution.id)

    response = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["extracted_model_answer_id"] is None
    # Still produces a real (if low-relevance) evaluation, not a crash.
    assert body["confidence_score"] is not None


async def test_inactive_and_deleted_model_answer_documents_are_never_selected(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """I. An exam has TWO model_answer documents: one inactive/soft-deleted
    (e.g. a superseded re-upload) and one genuinely active — only the
    active one may ever be selected."""
    await create_test_user(db_session, username="scopeteacher_i", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="SCOPEINACT")
    uploader = await create_test_user(db_session, username="scopeuploader_i")
    student = await create_test_user(db_session, username="scopestudent_i")

    exam = await _create_exam_under(db_session, institution, code="SCOPEINACTEXAM")

    qp_document = OfficialExamDocument(
        institution_id=exam.institution_id,
        exam_id=exam.id,
        uploaded_by=uploader.id,
        document_type="question_paper",
        original_filename="qp.pdf",
        mime_type="application/pdf",
        file_size_bytes=10,
        ocr_status="completed",
    )
    stale_ma_document = OfficialExamDocument(
        institution_id=exam.institution_id,
        exam_id=exam.id,
        uploaded_by=uploader.id,
        document_type="model_answer",
        original_filename="ma_v1_superseded.pdf",
        mime_type="application/pdf",
        file_size_bytes=10,
        ocr_status="completed",
        is_active=False,
    )
    active_ma_document = OfficialExamDocument(
        institution_id=exam.institution_id,
        exam_id=exam.id,
        uploaded_by=uploader.id,
        document_type="model_answer",
        original_filename="ma_v2_active.pdf",
        mime_type="application/pdf",
        file_size_bytes=10,
        ocr_status="completed",
        is_active=True,
    )
    db_session.add_all([qp_document, stale_ma_document, active_ma_document])
    await db_session.flush()

    question = ExtractedQuestion(
        institution_id=exam.institution_id,
        document_id=qp_document.id,
        question_number="1",
        question_text=_QUESTION_TEXT,
        raw_ocr_text=_QUESTION_TEXT,
        final_marks=Decimal("10.00"),
        display_order=0,
    )
    stale_model_answer = ExtractedModelAnswer(
        institution_id=exam.institution_id,
        document_id=stale_ma_document.id,
        question_number="1",
        answer_text="The SUPERSEDED, stale model answer — must never be selected.",
        raw_ocr_text="stale",
        display_order=0,
    )
    active_model_answer = ExtractedModelAnswer(
        institution_id=exam.institution_id,
        document_id=active_ma_document.id,
        question_number="1",
        answer_text="The current, correct model answer.",
        raw_ocr_text="active",
        display_order=0,
    )
    db_session.add_all([question, stale_model_answer, active_model_answer])
    await db_session.flush()

    exam_session = await _seed_exam_session_and_script(
        db_session,
        exam=exam,
        uploader=uploader,
        student=student,
        answer_text="Q1) An answer to compare against the active model answer.",
    )
    await db_session.commit()
    await db_session.refresh(question)
    await db_session.refresh(stale_model_answer)
    await db_session.refresh(active_model_answer)
    await db_session.refresh(exam_session)

    token = await _login(client, "scopeteacher_i")
    headers = _institution_headers(token, institution.id)

    response = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["extracted_model_answer_id"] == str(active_model_answer.id)
    assert body["extracted_model_answer_id"] != str(stale_model_answer.id)


async def test_soft_deleted_model_answer_row_is_never_selected(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """I. (variant) The `ExtractedModelAnswer` row itself is soft-deleted
    even though its parent document is active — must fall back to no
    model answer rather than resurrecting the deleted row."""
    await create_test_user(db_session, username="scopeteacher_i2", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="SCOPESOFTDEL")
    uploader = await create_test_user(db_session, username="scopeuploader_i2")
    student = await create_test_user(db_session, username="scopestudent_i2")

    exam = await _create_exam_under(db_session, institution, code="SCOPESOFTDELEXAM")
    question, model_answer, _ = await _seed_question_and_model_answer(
        db_session,
        exam=exam,
        uploader=uploader,
        question_number="1",
        model_answer_text="This model answer row will be soft-deleted.",
    )
    model_answer.deleted_at = datetime.now(UTC)
    exam_session = await _seed_exam_session_and_script(
        db_session,
        exam=exam,
        uploader=uploader,
        student=student,
        answer_text="Q1) An answer with a soft-deleted model answer on file.",
    )
    await db_session.commit()
    await db_session.refresh(question)
    await db_session.refresh(exam_session)

    token = await _login(client, "scopeteacher_i2")
    headers = _institution_headers(token, institution.id)

    response = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["extracted_model_answer_id"] is None


async def test_question_from_a_different_exam_than_the_session_is_rejected(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """Defensive check added alongside the fix: a caller must not be able
    to evaluate a question from Exam A against an ExamSession belonging to
    Exam B — this is rejected before any model-answer lookup happens."""
    await create_test_user(db_session, username="scopeteacher_x", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="SCOPEXEXAM")
    uploader = await create_test_user(db_session, username="scopeuploader_x2")
    student = await create_test_user(db_session, username="scopestudent_x2")

    exam1 = await _create_exam_under(db_session, institution, code="SCOPEXEXAM1")
    exam2 = await _create_exam_under(db_session, institution, code="SCOPEXEXAM2")

    question1, _, _ = await _seed_question_and_model_answer(
        db_session,
        exam=exam1,
        uploader=uploader,
        question_number="1",
        model_answer_text="Exam one's model answer.",
    )
    exam_session2 = await _seed_exam_session_and_script(
        db_session,
        exam=exam2,
        uploader=uploader,
        student=student,
        answer_text="Q1) An answer for exam two.",
    )
    await db_session.commit()
    await db_session.refresh(question1)
    await db_session.refresh(exam_session2)

    token = await _login(client, "scopeteacher_x")
    headers = _institution_headers(token, institution.id)

    # question1 belongs to exam1, exam_session2 belongs to exam2 — mismatch.
    response = await client.post(
        "/api/v1/answer-evaluations",
        json={
            "exam_session_id": str(exam_session2.id),
            "extracted_question_id": str(question1.id),
        },
        headers=headers,
    )

    assert response.status_code == 422


async def test_existing_single_exam_workflow_still_succeeds_after_the_fix(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """J. The ordinary, single-exam golden path (no collisions at all)
    still works exactly as before the fix."""
    await create_test_user(db_session, username="scopeteacher_j", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="SCOPEGOLDEN")
    uploader = await create_test_user(db_session, username="scopeuploader_j")
    student = await create_test_user(db_session, username="scopestudent_j")

    exam = await _create_exam_under(db_session, institution, code="SCOPEGOLDENEXAM")
    question, model_answer, _ = await _seed_question_and_model_answer(
        db_session,
        exam=exam,
        uploader=uploader,
        question_number="1",
        model_answer_text=(
            "Photosynthesis is the process by which green plants convert light "
            "energy into chemical energy using chlorophyll in their leaves."
        ),
    )
    exam_session = await _seed_exam_session_and_script(
        db_session,
        exam=exam,
        uploader=uploader,
        student=student,
        answer_text=(
            "Q1) Photosynthesis is how green plants convert light energy into "
            "chemical energy using chlorophyll in their leaves."
        ),
    )
    await db_session.commit()
    await db_session.refresh(question)
    await db_session.refresh(model_answer)
    await db_session.refresh(exam_session)

    token = await _login(client, "scopeteacher_j")
    headers = _institution_headers(token, institution.id)

    response = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["extracted_model_answer_id"] == str(model_answer.id)
    assert body["confidence_tier"] in ("high", "medium", "low")
