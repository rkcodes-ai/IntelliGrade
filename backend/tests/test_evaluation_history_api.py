"""EvaluationHistory API tests: create, get, list only — no update/delete route exists.

`ExamSession` and `AnswerKey` are sibling Module 04 models built by other
agents in the same implementation wave (both real by the time this file was
written). `_create_exam_context` builds the full Institution->Campus->
Department->Program->Course->SubjectCategory->Subject->AssessmentType/
Status->Assessment->Batch->Section->Exam chain directly via the ORM,
mirroring `test_exam_sessions_api.py`'s `_create_exam` helper; a `Question`
(and its lookup rows) is built under the same institution/subject so an
`AnswerKey` can reference it, mirroring `test_answer_keys_api.py`.
"""

import uuid
from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer_key import AnswerKey
from app.models.assessment import Assessment
from app.models.assessment_status import AssessmentStatus
from app.models.assessment_type import AssessmentType
from app.models.batch import Batch
from app.models.bloom_taxonomy_level import BloomTaxonomyLevel
from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.difficulty_level import DifficultyLevel
from app.models.exam import Exam
from app.models.exam_session import ExamSession
from app.models.institution import Institution
from app.models.program import Program
from app.models.question import Question
from app.models.question_category import QuestionCategory
from app.models.question_type import QuestionType
from app.models.section import Section
from app.models.subject import Subject
from app.models.subject_category import SubjectCategory
from app.models.user import User
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


class _ExamContext:
    """A persisted Institution/Subject/Exam chain, so a test can build both
    an `ExamSession` (via `Exam`) and a `Question`/`AnswerKey` (via
    `Subject`) under the same tenant."""

    def __init__(self, institution: Institution, subject: Subject, exam: Exam):
        self.institution = institution
        self.subject = subject
        self.exam = exam


async def _create_exam_context(db_session: AsyncSession, *, code: str) -> _ExamContext:
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
    await db_session.refresh(institution)
    await db_session.refresh(subject)
    await db_session.refresh(exam)
    return _ExamContext(institution, subject, exam)


async def _create_exam_session(
    db_session: AsyncSession, ctx: _ExamContext, student: User
) -> ExamSession:
    exam_session = ExamSession(
        institution_id=ctx.institution.id, exam_id=ctx.exam.id, student_user_id=student.id
    )
    db_session.add(exam_session)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(exam_session)
    return exam_session


async def _create_answer_key(
    db_session: AsyncSession, ctx: _ExamContext, *, code: str
) -> AnswerKey:
    category = QuestionCategory(
        institution_id=ctx.institution.id, code=f"QC-{code}", name=f"Category {code}"
    )
    question_type = QuestionType(
        institution_id=ctx.institution.id, code=f"QT-{code}", name=f"Type {code}"
    )
    difficulty = DifficultyLevel(
        institution_id=ctx.institution.id,
        code=f"DL-{code}",
        name=f"Difficulty {code}",
        level_order=1,
    )
    bloom = BloomTaxonomyLevel(
        institution_id=ctx.institution.id, code=f"BL-{code}", name=f"Bloom {code}", level_order=1
    )
    db_session.add_all([category, question_type, difficulty, bloom])
    await db_session.flush()

    question = Question(
        institution_id=ctx.institution.id,
        subject_id=ctx.subject.id,
        question_category_id=category.id,
        question_type_id=question_type.id,
        difficulty_level_id=difficulty.id,
        bloom_level_id=bloom.id,
        question_text=f"Question text {code}",
        marks=Decimal("5.00"),
    )
    db_session.add(question)
    await db_session.flush()

    answer_key = AnswerKey(
        institution_id=ctx.institution.id,
        question_id=question.id,
        reference_answer=f"Reference answer {code}.",
    )
    db_session.add(answer_key)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(answer_key)
    return answer_key


def _payload(exam_session_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "exam_session_id": str(exam_session_id),
        "evaluator_type": "human",
        "score": "8.50",
        "notes": "Reviewed manually.",
    }
    payload.update(overrides)
    return payload


async def test_create_evaluation_history_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ehadmin1", role=seed_rbac["super_admin"])
    ctx = await _create_exam_context(db_session, code="CREATE")
    student = await create_test_user(db_session, username="ehstud1")
    exam_session = await _create_exam_session(db_session, ctx, student)
    answer_key = await _create_answer_key(db_session, ctx, code="CREATE")
    token = await _login(client, "ehadmin1")

    response = await client.post(
        "/api/v1/evaluation-history",
        json=_payload(
            exam_session.id,
            answer_key_id=str(answer_key.id),
            evaluator_user_id=str(student.id),
        ),
        headers=_institution_headers(token, ctx.institution.id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["exam_session_id"] == str(exam_session.id)
    assert body["answer_key_id"] == str(answer_key.id)
    assert body["evaluator_type"] == "human"
    assert body["score"] == "8.50"


async def test_create_evaluation_history_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ehadmin2", role=seed_rbac["super_admin"])
    ctx = await _create_exam_context(db_session, code="NOHEADER")
    student = await create_test_user(db_session, username="ehstud2")
    exam_session = await _create_exam_session(db_session, ctx, student)
    token = await _login(client, "ehadmin2")

    response = await client.post(
        "/api/v1/evaluation-history",
        json=_payload(exam_session.id),
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_evaluation_history_rejects_nonexistent_exam_session(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ehadmin3", role=seed_rbac["super_admin"])
    ctx = await _create_exam_context(db_session, code="BADPARENT")
    token = await _login(client, "ehadmin3")

    response = await client.post(
        "/api/v1/evaluation-history",
        json=_payload(uuid.uuid4()),
        headers=_institution_headers(token, ctx.institution.id),
    )

    assert response.status_code == 404


async def test_non_privileged_role_cannot_create_evaluation_history(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ehstudent1", role=seed_rbac["student"])
    ctx = await _create_exam_context(db_session, code="FORBIDDEN")
    student = await create_test_user(db_session, username="ehstud3")
    exam_session = await _create_exam_session(db_session, ctx, student)
    token = await _login(client, "ehstudent1")

    response = await client.post(
        "/api/v1/evaluation-history",
        json=_payload(exam_session.id),
        headers=_institution_headers(token, ctx.institution.id),
    )

    assert response.status_code == 403


async def test_evaluation_history_get_and_list(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ehadmin4", role=seed_rbac["super_admin"])
    ctx = await _create_exam_context(db_session, code="GETLIST")
    student = await create_test_user(db_session, username="ehstud4")
    exam_session = await _create_exam_session(db_session, ctx, student)
    token = await _login(client, "ehadmin4")
    headers = _institution_headers(token, ctx.institution.id)

    create_response = await client.post(
        "/api/v1/evaluation-history", json=_payload(exam_session.id), headers=headers
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]

    get_response = await client.get(f"/api/v1/evaluation-history/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["score"] == "8.50"

    list_response = await client.get("/api/v1/evaluation-history", headers=headers)
    assert list_response.status_code == 200
    assert any(item["id"] == entity_id for item in list_response.json()["items"])


async def test_evaluation_history_get_nonexistent_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ehadmin5", role=seed_rbac["super_admin"])
    ctx = await _create_exam_context(db_session, code="404")
    token = await _login(client, "ehadmin5")

    response = await client.get(
        f"/api/v1/evaluation-history/{uuid.uuid4()}",
        headers=_institution_headers(token, ctx.institution.id),
    )
    assert response.status_code == 404


async def test_list_evaluation_history_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ehadmin6", role=seed_rbac["super_admin"])
    ctx = await _create_exam_context(db_session, code="LIST")
    token = await _login(client, "ehadmin6")
    headers = _institution_headers(token, ctx.institution.id)

    for i in range(5):
        student = await create_test_user(db_session, username=f"ehliststud{i}")
        exam_session = await _create_exam_session(db_session, ctx, student)
        response = await client.post(
            "/api/v1/evaluation-history", json=_payload(exam_session.id), headers=headers
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/evaluation-history?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] >= 5
