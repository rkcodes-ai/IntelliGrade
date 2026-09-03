"""AnswerEvaluation tests: the AI evaluation orchestration
(`AnswerEvaluationService.evaluate_question`) and the Teacher Review
actions (confirm/override/reject/rerun, Module 06/07), exercised through
the real API + real `LexicalHeuristicProvider` (no mocking of the AI
layer — same "genuine, not faked" convention as Module 05's
real-Tesseract tests)."""

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_provider import AIProvider
from app.models.answer_script import AnswerScript
from app.models.exam_session import ExamSession
from app.models.extracted_model_answer import ExtractedModelAnswer
from app.models.extracted_question import ExtractedQuestion
from app.models.official_exam_document import OfficialExamDocument
from app.services.exam_result_service import ExamResultService
from tests.conftest import auth_headers, create_test_user
from tests.test_official_exam_documents_api import _create_exam, _login

_QUESTION_TEXT = "Explain the process of photosynthesis in plants."
_MODEL_ANSWER_TEXT = (
    "Photosynthesis is the process by which green plants convert light energy "
    "into chemical energy using chlorophyll in their leaves."
)
_GOOD_STUDENT_ANSWER = (
    "Q1) Photosynthesis is how green plants convert light energy into chemical "
    "energy using chlorophyll in their leaves."
)


def _institution_headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


async def _seed_ai_provider(db_session: AsyncSession) -> AIProvider:
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


async def _build_evaluation_fixtures(
    db_session: AsyncSession, *, code: str, student_answer_text: str = _GOOD_STUDENT_ANSWER
) -> tuple[ExamSession, ExtractedQuestion, ExtractedModelAnswer]:
    exam = await _create_exam(db_session, code=code)
    uploader = await create_test_user(db_session, username=f"evaluploader_{code.lower()}")
    student = await create_test_user(db_session, username=f"evalstudent_{code.lower()}")

    exam_session = ExamSession(
        institution_id=exam.institution_id, exam_id=exam.id, student_user_id=student.id
    )
    db_session.add(exam_session)
    await db_session.flush()

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
    ma_document = OfficialExamDocument(
        institution_id=exam.institution_id,
        exam_id=exam.id,
        uploaded_by=uploader.id,
        document_type="model_answer",
        original_filename="ma.pdf",
        mime_type="application/pdf",
        file_size_bytes=10,
        ocr_status="completed",
    )
    db_session.add_all([qp_document, ma_document])
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
    model_answer = ExtractedModelAnswer(
        institution_id=exam.institution_id,
        document_id=ma_document.id,
        question_number="1",
        answer_text=_MODEL_ANSWER_TEXT,
        raw_ocr_text=_MODEL_ANSWER_TEXT,
        display_order=0,
    )
    db_session.add_all([question, model_answer])
    await db_session.flush()

    answer_script = AnswerScript(
        institution_id=exam.institution_id,
        exam_session_id=exam_session.id,
        uploaded_by=uploader.id,
        original_filename="script.pdf",
        mime_type="application/pdf",
        file_size_bytes=10,
        checksum_sha256="0" * 64,
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
                            "lines": [
                                {"text": student_answer_text, "reading_order": 0, "words": []}
                            ],
                        }
                    ],
                }
            ],
        },
    )
    db_session.add(answer_script)
    await db_session.commit()
    await db_session.refresh(exam_session)
    await db_session.refresh(question)
    await db_session.refresh(model_answer)
    return exam_session, question, model_answer


async def test_trigger_answer_evaluation_produces_all_seven_signals(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="evalteacher1", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    exam_session, question, _ = await _build_evaluation_fixtures(db_session, code="EVALGOOD")
    token = await _login(client, "evalteacher1")
    headers = _institution_headers(token, exam_session.institution_id)

    response = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["semantic_similarity_score"] is not None
    assert body["keyword_match_score"] is not None
    assert body["concept_match_score"] is not None
    assert body["reasoning_score"] is not None
    assert body["completeness_score"] is not None
    assert body["relevance_score"] is not None
    assert body["confidence_score"] is not None
    assert body["confidence_tier"] in ("high", "medium", "low")
    assert body["max_marks"] == "10.00" or float(body["max_marks"]) == 10.0
    assert body["suggested_marks"] is not None
    assert body["student_answer_text"] is not None
    assert "Photosynthesis" in body["student_answer_text"]


async def test_trigger_answer_evaluation_is_idempotent_upsert(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="evalteacher2", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    exam_session, question, _ = await _build_evaluation_fixtures(db_session, code="EVALIDEMPOTENT")
    token = await _login(client, "evalteacher2")
    headers = _institution_headers(token, exam_session.institution_id)

    payload = {"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)}
    first = await client.post("/api/v1/answer-evaluations", json=payload, headers=headers)
    second = await client.post("/api/v1/answer-evaluations", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


async def test_trigger_answer_evaluation_rejects_question_without_marks(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="evalteacher3", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    exam_session, question, _ = await _build_evaluation_fixtures(db_session, code="EVALNOMARKS")
    question.final_marks = None
    await db_session.commit()
    token = await _login(client, "evalteacher3")
    headers = _institution_headers(token, exam_session.institution_id)

    response = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )

    assert response.status_code == 422


async def test_confirm_answer_evaluation_sets_final_marks_from_suggested(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="evalteacher4", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    exam_session, question, _ = await _build_evaluation_fixtures(db_session, code="EVALCONFIRM")
    token = await _login(client, "evalteacher4")
    headers = _institution_headers(token, exam_session.institution_id)

    created = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )
    evaluation_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/answer-evaluations/{evaluation_id}/confirm", headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["review_status"] == "teacher_confirmed"
    assert body["final_marks"] == body["suggested_marks"]
    assert body["reviewed_by"] is not None


async def test_override_answer_evaluation_sets_custom_marks(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="evalteacher5", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    exam_session, question, _ = await _build_evaluation_fixtures(db_session, code="EVALOVERRIDE")
    token = await _login(client, "evalteacher5")
    headers = _institution_headers(token, exam_session.institution_id)

    created = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )
    evaluation_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/answer-evaluations/{evaluation_id}/override",
        json={"final_marks": "7.50", "notes": "Partial credit for missing chloroplast detail."},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["review_status"] == "teacher_overridden"
    assert float(body["final_marks"]) == 7.5
    assert body["notes"] == "Partial credit for missing chloroplast detail."


async def test_override_answer_evaluation_rejects_marks_above_maximum(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="evalteacher6", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    exam_session, question, _ = await _build_evaluation_fixtures(db_session, code="EVALOVERMAX")
    token = await _login(client, "evalteacher6")
    headers = _institution_headers(token, exam_session.institution_id)

    created = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )
    evaluation_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/answer-evaluations/{evaluation_id}/override",
        json={"final_marks": "99.00"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_low_confidence_evaluation_forces_pending_review(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="evalteacher7", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    exam_session, question, _ = await _build_evaluation_fixtures(
        db_session, code="EVALLOWCONF", student_answer_text="Q1) The stock market crashed in 1929."
    )
    token = await _login(client, "evalteacher7")
    headers = _institution_headers(token, exam_session.institution_id)

    response = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["confidence_tier"] == "low"
    assert body["review_status"] == "pending_review"
    assert body["final_marks"] is None


async def test_non_privileged_role_cannot_trigger_evaluation(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="evalstudent1", role=seed_rbac["student"])
    await _seed_ai_provider(db_session)
    exam_session, question, _ = await _build_evaluation_fixtures(db_session, code="EVALFORBID")
    token = await _login(client, "evalstudent1")
    headers = _institution_headers(token, exam_session.institution_id)

    response = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )

    assert response.status_code == 403


async def test_list_answer_evaluations_pagination_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="evalteacher8", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    exam_session, question, _ = await _build_evaluation_fixtures(db_session, code="EVALLIST")
    token = await _login(client, "evalteacher8")
    headers = _institution_headers(token, exam_session.institution_id)

    await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )

    response = await client.get("/api/v1/answer-evaluations", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert body["total"] == 1


async def test_reject_answer_evaluation_clears_final_marks_and_requires_reason(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="evalteacher9", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    exam_session, question, _ = await _build_evaluation_fixtures(db_session, code="EVALREJECT")
    token = await _login(client, "evalteacher9")
    headers = _institution_headers(token, exam_session.institution_id)

    created = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )
    evaluation_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/answer-evaluations/{evaluation_id}/reject",
        json={"reason": "AI misread the diagram reference in the student's answer."},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["review_status"] == "teacher_rejected"
    assert body["final_marks"] is None
    assert body["suggested_marks"] is not None  # original AI marks are never overwritten
    assert body["notes"] == "AI misread the diagram reference in the student's answer."
    assert body["reviewed_by"] is not None


async def test_reject_answer_evaluation_requires_reason_field(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="evalteacher10", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    exam_session, question, _ = await _build_evaluation_fixtures(
        db_session, code="EVALREJECTNOREASON"
    )
    token = await _login(client, "evalteacher10")
    headers = _institution_headers(token, exam_session.institution_id)

    created = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )
    evaluation_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/answer-evaluations/{evaluation_id}/reject", json={}, headers=headers
    )
    assert response.status_code == 422


async def test_trigger_after_teacher_review_does_not_silently_overwrite(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="evalteacher11", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    exam_session, question, _ = await _build_evaluation_fixtures(db_session, code="EVALNOOVERWRITE")
    token = await _login(client, "evalteacher11")
    headers = _institution_headers(token, exam_session.institution_id)
    payload = {"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)}

    created = await client.post("/api/v1/answer-evaluations", json=payload, headers=headers)
    evaluation_id = created.json()["id"]
    override_resp = await client.post(
        f"/api/v1/answer-evaluations/{evaluation_id}/override",
        json={"final_marks": "3.00", "notes": "Manual re-grade."},
        headers=headers,
    )
    assert override_resp.json()["review_status"] == "teacher_overridden"

    replayed = await client.post("/api/v1/answer-evaluations", json=payload, headers=headers)
    assert replayed.status_code == 201
    body = replayed.json()
    assert body["id"] == evaluation_id
    assert body["review_status"] == "teacher_overridden"
    assert float(body["final_marks"]) == 3.0


async def test_rerun_answer_evaluation_recomputes_over_a_teacher_reviewed_row(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="evalteacher12", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    exam_session, question, _ = await _build_evaluation_fixtures(db_session, code="EVALRERUN")
    token = await _login(client, "evalteacher12")
    headers = _institution_headers(token, exam_session.institution_id)
    payload = {"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)}

    created = await client.post("/api/v1/answer-evaluations", json=payload, headers=headers)
    evaluation_id = created.json()["id"]
    await client.post(
        f"/api/v1/answer-evaluations/{evaluation_id}/override",
        json={"final_marks": "1.00", "notes": "Manual re-grade."},
        headers=headers,
    )

    rerun_resp = await client.post(
        f"/api/v1/answer-evaluations/{evaluation_id}/rerun", headers=headers
    )

    assert rerun_resp.status_code == 200
    body = rerun_resp.json()
    assert body["id"] == evaluation_id
    # A fresh AI pass overwrites the review state — same tier-derived
    # review_status a first-time trigger would produce.
    assert body["review_status"] in ("auto_suggested", "pending_confirmation", "pending_review")
    assert body["reviewed_by"] is None
    assert body["notes"] is None


async def test_locked_exam_result_blocks_further_evaluation_actions(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="evalteacher13", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    exam_session, question, _ = await _build_evaluation_fixtures(db_session, code="EVALLOCKED")
    token = await _login(client, "evalteacher13")
    headers = _institution_headers(token, exam_session.institution_id)
    payload = {"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)}

    created = await client.post("/api/v1/answer-evaluations", json=payload, headers=headers)
    evaluation_id = created.json()["id"]
    await client.post(f"/api/v1/answer-evaluations/{evaluation_id}/confirm", headers=headers)

    result_service = ExamResultService(db_session)
    result = await result_service.finalize_student(
        exam_session.institution_id, exam_session.id, actor_id=None
    )
    await result_service.approve(exam_session.institution_id, result.id, actor_id=None)
    await result_service.lock(exam_session.institution_id, result.id, actor_id=None)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/answer-evaluations/{evaluation_id}/override",
        json={"final_marks": "2.00"},
        headers=headers,
    )
    assert response.status_code == 409
