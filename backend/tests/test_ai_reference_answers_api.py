"""AIReferenceAnswer tests (AI Reference Answer Builder milestone) —
generation, structured-output validation, exam/subject/tenant isolation,
mark-aware scoring guidance, versioning, approval/rejection/regeneration,
evaluation-engine integration, traceability, provider-failure handling,
and RBAC. Exercised through the real API + the real, deterministic
`LexicalHeuristicProvider` (never a paid LLM call, per Phase 13's
"deterministic AI fixtures" requirement) — genuine, not faked, same
"no mocking of the AI layer" convention as `test_answer_evaluations_api.py`.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_provider import AIProvider
from app.models.ai_reference_answer import AIReferenceAnswer
from app.models.answer_evaluation import AnswerEvaluation
from app.models.audit_log import AuditLog
from app.models.extracted_model_answer import ExtractedModelAnswer
from app.models.extracted_question import ExtractedQuestion
from app.models.official_exam_document import OfficialExamDocument
from app.schemas.ai_reference_answer import ReferenceContentSchema
from app.services import ai_reference_answer_service as ai_reference_answer_service_module
from app.services.ai.base import AIProviderAdapter, ReferenceGenerationInput
from app.services.ai.exceptions import (
    AIProviderInvalidResponseError,
    AIProviderTimeoutError,
)
from tests.conftest import auth_headers, create_test_user
from tests.test_answer_evaluation_model_answer_scoping import (
    _create_exam_under,
    _create_institution,
    _seed_ai_provider,
    _seed_exam_session_and_script,
    _seed_question_and_model_answer,
)
from tests.test_official_exam_documents_api import _login

_MODEL_ANSWER_TEXT = (
    "Photosynthesis is the process by which green plants convert light energy "
    "into chemical energy using chlorophyll. This occurs because carbon "
    "dioxide and water react in sunlight to produce glucose and oxygen."
)


def _institution_headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


async def _seed_verified_question_and_model_answer(
    db_session: AsyncSession,
    *,
    exam,
    uploader,
    question_number: str = "1",
    max_marks: str = "10.00",
):
    question, model_answer, ma_document = await _seed_question_and_model_answer(
        db_session,
        exam=exam,
        uploader=uploader,
        question_number=question_number,
        model_answer_text=_MODEL_ANSWER_TEXT,
    )
    question.final_marks = Decimal(max_marks)
    question.verification_status = "verified"
    model_answer.verification_status = "verified"
    await db_session.flush()
    return question, model_answer, ma_document


class _FakeFailingProvider(AIProviderAdapter):
    """A real, in-memory `AIProviderAdapter` implementation (not a mock
    library patch) used only to exercise `ReferenceAnswerService`'s
    provider-failure handling deterministically — raises whatever
    exception it's constructed with, imitating provider timeout/rate-
    limit/invalid-response failures without a real network call."""

    provider_code = "fake_failing"
    is_implemented = True

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def evaluate(self, data):  # pragma: no cover - unused by these tests
        raise self._exc

    def generate_reference(self, data: ReferenceGenerationInput) -> ReferenceContentSchema:
        raise self._exc


async def test_generate_reference_produces_real_structured_content(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """1. Correct question/model-answer pairing. 7/8/9. Required concepts,
    alternative answers, equivalent terms are all present as real (if
    honestly-empty-where-appropriate) fields."""
    await create_test_user(db_session, username="refteacher1", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="REFGEN")
    uploader = await create_test_user(db_session, username="refuploader1")
    exam = await _create_exam_under(db_session, institution, code="REFGENEXAM")
    question, model_answer, _ = await _seed_verified_question_and_model_answer(
        db_session, exam=exam, uploader=uploader
    )
    await db_session.commit()
    await db_session.refresh(question)

    token = await _login(client, "refteacher1")
    headers = _institution_headers(token, institution.id)

    response = await client.post(
        "/api/v1/ai-reference-answers",
        json={"extracted_question_id": str(question.id)},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending_verification"
    assert body["version"] == 1
    assert body["is_current"] is True
    assert body["synthesized_reference_answer"] == _MODEL_ANSWER_TEXT
    assert len(body["structured_content"]["required_concepts"]) > 0
    assert body["structured_content"]["alternative_valid_answers"] == []
    assert body["structured_content"]["equivalent_terms"] == []
    assert body["maximum_marks"] == "10.00"
    assert body["marks_source"] == "final_marks"
    assert body["has_conflict_flag"] is False


async def test_generate_reference_requires_verified_question(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """Phase 2: must not operate on unverified official documents."""
    await create_test_user(db_session, username="refteacher2", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="REFUNVER")
    uploader = await create_test_user(db_session, username="refuploader2")
    exam = await _create_exam_under(db_session, institution, code="REFUNVEREXAM")
    question, model_answer, _ = await _seed_question_and_model_answer(
        db_session, exam=exam, uploader=uploader, model_answer_text=_MODEL_ANSWER_TEXT
    )
    question.final_marks = Decimal("10.00")
    # Deliberately leave question.verification_status at its "pending" default.
    await db_session.commit()
    await db_session.refresh(question)

    token = await _login(client, "refteacher2")
    headers = _institution_headers(token, institution.id)

    response = await client.post(
        "/api/v1/ai-reference-answers",
        json={"extracted_question_id": str(question.id)},
        headers=headers,
    )
    assert response.status_code == 422


async def test_generate_reference_requires_verified_model_answer(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="refteacher3", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="REFMAUNVER")
    uploader = await create_test_user(db_session, username="refuploader3")
    exam = await _create_exam_under(db_session, institution, code="REFMAUNVEREXAM")
    question, model_answer, _ = await _seed_question_and_model_answer(
        db_session, exam=exam, uploader=uploader, model_answer_text=_MODEL_ANSWER_TEXT
    )
    question.final_marks = Decimal("10.00")
    question.verification_status = "verified"
    # Deliberately leave model_answer.verification_status at "pending".
    await db_session.commit()
    await db_session.refresh(question)

    token = await _login(client, "refteacher3")
    headers = _institution_headers(token, institution.id)

    response = await client.post(
        "/api/v1/ai-reference-answers",
        json={"extracted_question_id": str(question.id)},
        headers=headers,
    )
    assert response.status_code == 422


async def test_reference_generation_is_scoped_to_the_correct_exam(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """2/3. Cross-exam AND cross-subject isolation — reuses the exact
    scoping fix from the Model Answer correctness milestone."""
    await create_test_user(db_session, username="refteacher4", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="REFSCOPE")
    uploader = await create_test_user(db_session, username="refuploader4")

    exam1 = await _create_exam_under(db_session, institution, code="REFSCOPEEX1")
    exam2 = await _create_exam_under(db_session, institution, code="REFSCOPEEX2")
    question1, model_answer1, _ = await _seed_verified_question_and_model_answer(
        db_session, exam=exam1, uploader=uploader, question_number="1"
    )
    _, model_answer2, _ = await _seed_question_and_model_answer(
        db_session,
        exam=exam2,
        uploader=uploader,
        question_number="1",
        model_answer_text="Exam two's completely different official answer about volcanoes.",
    )
    model_answer2.verification_status = "verified"
    await db_session.commit()
    await db_session.refresh(question1)
    await db_session.refresh(model_answer1)

    token = await _login(client, "refteacher4")
    headers = _institution_headers(token, institution.id)

    response = await client.post(
        "/api/v1/ai-reference-answers",
        json={"extracted_question_id": str(question1.id)},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["extracted_model_answer_id"] == str(model_answer1.id)
    assert body["extracted_model_answer_id"] != str(model_answer2.id)
    assert body["synthesized_reference_answer"] == _MODEL_ANSWER_TEXT
    assert "volcanoes" not in body["synthesized_reference_answer"]


async def test_reference_generation_is_scoped_to_the_correct_tenant(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """4. Cross-tenant (multi-institution) isolation."""
    await create_test_user(db_session, username="refteacher5", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution_x = await _create_institution(db_session, code="REFTENX")
    institution_y = await _create_institution(db_session, code="REFTENY")
    uploader_x = await create_test_user(db_session, username="refuploaderx")
    uploader_y = await create_test_user(db_session, username="refuploadery")

    exam_x = await _create_exam_under(db_session, institution_x, code="REFTENXEX")
    exam_y = await _create_exam_under(db_session, institution_y, code="REFTENYEX")
    question_x, model_answer_x, _ = await _seed_verified_question_and_model_answer(
        db_session, exam=exam_x, uploader=uploader_x
    )
    await _seed_verified_question_and_model_answer(db_session, exam=exam_y, uploader=uploader_y)
    await db_session.commit()
    await db_session.refresh(question_x)

    token = await _login(client, "refteacher5")
    headers = _institution_headers(token, institution_x.id)

    response = await client.post(
        "/api/v1/ai-reference-answers",
        json={"extracted_question_id": str(question_x.id)},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["extracted_model_answer_id"] == str(model_answer_x.id)


async def test_reference_scoring_guidance_scales_with_maximum_marks(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """5. Maximum marks propagation (Phase 5: mark-aware depth)."""
    await create_test_user(db_session, username="refteacher6", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="REFMARKS")
    uploader = await create_test_user(db_session, username="refuploader6")
    exam = await _create_exam_under(db_session, institution, code="REFMARKSEXAM")
    question, _, _ = await _seed_verified_question_and_model_answer(
        db_session, exam=exam, uploader=uploader, max_marks="14.00"
    )
    await db_session.commit()
    await db_session.refresh(question)

    token = await _login(client, "refteacher6")
    headers = _institution_headers(token, institution.id)

    response = await client.post(
        "/api/v1/ai-reference-answers",
        json={"extracted_question_id": str(question.id)},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["maximum_marks"] == "14.00"
    assert len(body["structured_content"]["scoring_guidance"]) >= 4


async def test_generation_failure_persists_a_visible_failed_row_and_never_clobbers_current(
    db_session: AsyncSession, seed_rbac
) -> None:
    """6/11/12/13/14. Malformed/unavailable provider output must fail
    safely and visibly (service-level test using a real, deterministic
    fake adapter — see `_FakeFailingProvider` — for timeout/rate-limit/
    invalid-response, since these can't be triggered without a live,
    flaky network call)."""
    from app.services.ai_reference_answer_service import ReferenceAnswerService

    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="REFFAIL")
    uploader = await create_test_user(db_session, username="refuploader7")
    exam = await _create_exam_under(db_session, institution, code="REFFAILEXAM")
    question, _, _ = await _seed_verified_question_and_model_answer(
        db_session, exam=exam, uploader=uploader
    )
    await db_session.commit()
    await db_session.refresh(question)

    service = ReferenceAnswerService(db_session)

    for exc in (
        AIProviderTimeoutError("simulated timeout"),
        AIProviderInvalidResponseError("simulated malformed output"),
    ):
        fake = _FakeFailingProvider(exc)
        original_get_adapter = ai_reference_answer_service_module.get_provider_adapter
        ai_reference_answer_service_module.get_provider_adapter = (
            lambda code, _fake=fake: _fake  # noqa: ARG005
        )
        try:
            with pytest.raises(type(exc)):
                await service.generate(institution.id, question.id, actor_id=None, force=True)
        finally:
            ai_reference_answer_service_module.get_provider_adapter = original_get_adapter

    query = select(AIReferenceAnswer).where(
        AIReferenceAnswer.extracted_question_id == question.id,
        AIReferenceAnswer.status == "generation_failed",
    )
    failed_rows = (await db_session.execute(query)).scalars().all()
    assert len(failed_rows) == 2  # both failures left a real, queryable audit trail
    assert all(row.is_current is False for row in failed_rows)  # never became "current"
    assert failed_rows[0].generation_error is not None


async def test_missing_credentials_produces_configuration_error_and_failed_row(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """15. Missing credentials (real, using the real credential-gated
    OpenAIProvider — this suite never fabricates an API key)."""
    await create_test_user(db_session, username="refteacher8", role=seed_rbac["super_admin"])
    # Deliberately NOT `_seed_ai_provider()` (lexical_heuristic, also
    # `is_default=True`) — this test needs `_resolve_provider_code` to
    # unambiguously resolve to the real, credential-gated OpenAI provider.
    openai_provider = AIProvider(
        code="openai", name="OpenAI", is_enabled=True, is_implemented=True, is_default=True
    )
    db_session.add(openai_provider)
    institution = await _create_institution(db_session, code="REFNOCREDS")
    uploader = await create_test_user(db_session, username="refuploader8")
    exam = await _create_exam_under(db_session, institution, code="REFNOCREDSEXAM")
    question, _, _ = await _seed_verified_question_and_model_answer(
        db_session, exam=exam, uploader=uploader
    )
    await db_session.commit()
    await db_session.refresh(question)

    token = await _login(client, "refteacher8")
    headers = _institution_headers(token, institution.id)

    response = await client.post(
        "/api/v1/ai-reference-answers",
        json={"extracted_question_id": str(question.id)},
        headers=headers,
    )
    assert response.status_code == 400  # AIProviderConfigurationError

    query = select(AIReferenceAnswer).where(
        AIReferenceAnswer.extracted_question_id == question.id,
        AIReferenceAnswer.status == "generation_failed",
    )
    failed = (await db_session.execute(query)).scalars().first()
    assert failed is not None
    assert "OPENAI_API_KEY" in (failed.generation_error or "")


async def test_regenerate_creates_new_version_and_supersedes_the_old_one(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """16/17. Regeneration + versioning."""
    await create_test_user(db_session, username="refteacher9", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="REFREGEN")
    uploader = await create_test_user(db_session, username="refuploader9")
    exam = await _create_exam_under(db_session, institution, code="REFREGENEXAM")
    question, _, _ = await _seed_verified_question_and_model_answer(
        db_session, exam=exam, uploader=uploader
    )
    await db_session.commit()
    await db_session.refresh(question)

    token = await _login(client, "refteacher9")
    headers = _institution_headers(token, institution.id)

    first = await client.post(
        "/api/v1/ai-reference-answers",
        json={"extracted_question_id": str(question.id)},
        headers=headers,
    )
    assert first.status_code == 201
    first_id = first.json()["id"]
    assert first.json()["version"] == 1

    second = await client.post(
        f"/api/v1/ai-reference-answers/by-question/{question.id}/regenerate", headers=headers
    )
    assert second.status_code == 201
    assert second.json()["version"] == 2
    assert second.json()["is_current"] is True
    assert second.json()["id"] != first_id

    first_row = await db_session.get(AIReferenceAnswer, uuid.UUID(first_id))
    await db_session.refresh(first_row)
    assert first_row.is_current is False  # superseded, but never deleted

    versions_resp = await client.get(
        f"/api/v1/ai-reference-answers/by-question/{question.id}/versions", headers=headers
    )
    assert len(versions_resp.json()) == 2


async def test_approve_and_reject_transitions(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """18/19. Approval + rejection."""
    await create_test_user(db_session, username="refteacher10", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="REFAPPROVE")
    uploader = await create_test_user(db_session, username="refuploader10")
    exam = await _create_exam_under(db_session, institution, code="REFAPPROVEEXAM")
    question, _, _ = await _seed_verified_question_and_model_answer(
        db_session, exam=exam, uploader=uploader
    )
    await db_session.commit()
    await db_session.refresh(question)

    token = await _login(client, "refteacher10")
    headers = _institution_headers(token, institution.id)

    created = await client.post(
        "/api/v1/ai-reference-answers",
        json={"extracted_question_id": str(question.id)},
        headers=headers,
    )
    reference_id = created.json()["id"]

    approved = await client.post(
        f"/api/v1/ai-reference-answers/{reference_id}/approve", headers=headers
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["verified_by"] is not None

    # A second, independent question (its own exam, so its own model-answer
    # document — sharing `exam` here would put two model_answer documents
    # under one exam and make the exam-scoped resolver's tiebreak
    # nondeterministic, which isn't what this test is checking) to test
    # rejection without reusing an already-approved row.
    exam2 = await _create_exam_under(db_session, institution, code="REFAPPROVEEXAM2")
    question2, _, _ = await _seed_verified_question_and_model_answer(
        db_session, exam=exam2, uploader=uploader, question_number="2"
    )
    await db_session.commit()
    await db_session.refresh(question2)
    created2 = await client.post(
        "/api/v1/ai-reference-answers",
        json={"extracted_question_id": str(question2.id)},
        headers=headers,
    )
    rejected = await client.post(
        f"/api/v1/ai-reference-answers/{created2.json()['id']}/reject",
        json={"reason": "The synthesized answer misrepresents chlorophyll's role."},
        headers=headers,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["rejection_reason"] == (
        "The synthesized answer misrepresents chlorophyll's role."
    )


async def test_evaluation_uses_the_approved_reference_and_records_traceability(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """20/21. Evaluation using the approved reference + evaluation<->
    reference traceability."""
    await create_test_user(db_session, username="refteacher11", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="REFEVALUSE")
    uploader = await create_test_user(db_session, username="refuploader11")
    student = await create_test_user(db_session, username="refstudent11")
    exam = await _create_exam_under(db_session, institution, code="REFEVALUSEEXAM")
    question, _, _ = await _seed_verified_question_and_model_answer(
        db_session, exam=exam, uploader=uploader
    )
    exam_session = await _seed_exam_session_and_script(
        db_session,
        exam=exam,
        uploader=uploader,
        student=student,
        answer_text=(
            "Q1) Photosynthesis converts light energy into chemical energy using "
            "chlorophyll, producing glucose and oxygen from carbon dioxide and water."
        ),
    )
    await db_session.commit()
    await db_session.refresh(question)
    await db_session.refresh(exam_session)

    token = await _login(client, "refteacher11")
    headers = _institution_headers(token, institution.id)

    created = await client.post(
        "/api/v1/ai-reference-answers",
        json={"extracted_question_id": str(question.id)},
        headers=headers,
    )
    reference_id = created.json()["id"]
    await client.post(f"/api/v1/ai-reference-answers/{reference_id}/approve", headers=headers)

    evaluation_resp = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )
    assert evaluation_resp.status_code == 201
    body = evaluation_resp.json()
    assert body["used_legacy_reference"] is False
    assert body["ai_reference_answer_id"] == reference_id


async def test_evaluation_without_approved_reference_uses_visible_legacy_fallback(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """9 (Phase 9 fallback): no reference generated at all -> legacy
    fallback is used, and it is explicitly visible on the row."""
    await create_test_user(db_session, username="refteacher12", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="REFLEGACY")
    uploader = await create_test_user(db_session, username="refuploader12")
    student = await create_test_user(db_session, username="refstudent12")
    exam = await _create_exam_under(db_session, institution, code="REFLEGACYEXAM")
    question, _, _ = await _seed_verified_question_and_model_answer(
        db_session, exam=exam, uploader=uploader
    )
    exam_session = await _seed_exam_session_and_script(
        db_session,
        exam=exam,
        uploader=uploader,
        student=student,
        answer_text="Q1) Some answer text.",
    )
    await db_session.commit()
    await db_session.refresh(question)
    await db_session.refresh(exam_session)

    token = await _login(client, "refteacher12")
    headers = _institution_headers(token, institution.id)

    # No AI reference answer generated at all for this question.
    evaluation_resp = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )
    assert evaluation_resp.status_code == 201
    body = evaluation_resp.json()
    assert body["used_legacy_reference"] is True
    assert body["ai_reference_answer_id"] is None


async def test_historical_evaluation_retains_its_original_reference_version_after_regeneration(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """22. Historical evaluations retain their original reference version
    even after the question's reference is regenerated."""
    await create_test_user(db_session, username="refteacher13", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="REFHIST")
    uploader = await create_test_user(db_session, username="refuploader13")
    student = await create_test_user(db_session, username="refstudent13")
    exam = await _create_exam_under(db_session, institution, code="REFHISTEXAM")
    question, _, _ = await _seed_verified_question_and_model_answer(
        db_session, exam=exam, uploader=uploader
    )
    exam_session = await _seed_exam_session_and_script(
        db_session, exam=exam, uploader=uploader, student=student, answer_text="Q1) An answer."
    )
    await db_session.commit()
    await db_session.refresh(question)
    await db_session.refresh(exam_session)

    token = await _login(client, "refteacher13")
    headers = _institution_headers(token, institution.id)

    first_reference = await client.post(
        "/api/v1/ai-reference-answers",
        json={"extracted_question_id": str(question.id)},
        headers=headers,
    )
    first_reference_id = first_reference.json()["id"]
    await client.post(
        f"/api/v1/ai-reference-answers/{first_reference_id}/approve", headers=headers
    )

    evaluation_resp = await client.post(
        "/api/v1/answer-evaluations",
        json={"exam_session_id": str(exam_session.id), "extracted_question_id": str(question.id)},
        headers=headers,
    )
    assert evaluation_resp.json()["ai_reference_answer_id"] == first_reference_id

    # Regenerate -> a NEW current version exists, but the past evaluation's
    # pointer must still resolve to the ORIGINAL (now-superseded) version.
    await client.post(
        f"/api/v1/ai-reference-answers/by-question/{question.id}/regenerate", headers=headers
    )

    evaluation_query = select(AnswerEvaluation).where(
        AnswerEvaluation.institution_id == institution.id,
        AnswerEvaluation.exam_session_id == exam_session.id,
        AnswerEvaluation.extracted_question_id == question.id,
    )
    evaluation_row = (await db_session.execute(evaluation_query)).scalars().first()
    assert str(evaluation_row.ai_reference_answer_id) == first_reference_id


async def test_non_privileged_role_cannot_generate_reference(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """23. RBAC."""
    await create_test_user(db_session, username="refstudentrole", role=seed_rbac["student"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="REFRBAC")
    uploader = await create_test_user(db_session, username="refuploader14")
    exam = await _create_exam_under(db_session, institution, code="REFRBACEXAM")
    question, _, _ = await _seed_verified_question_and_model_answer(
        db_session, exam=exam, uploader=uploader
    )
    await db_session.commit()
    await db_session.refresh(question)

    token = await _login(client, "refstudentrole")
    headers = _institution_headers(token, institution.id)

    response = await client.post(
        "/api/v1/ai-reference-answers",
        json={"extracted_question_id": str(question.id)},
        headers=headers,
    )
    assert response.status_code == 403


async def test_generation_and_approval_write_real_audit_log_entries(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """24. Audit logging — real `AuditLog` rows, not just a return value."""
    await create_test_user(db_session, username="refteacher16", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="REFAUDIT")
    uploader = await create_test_user(db_session, username="refuploader16")
    exam = await _create_exam_under(db_session, institution, code="REFAUDITEXAM")
    question, _, _ = await _seed_verified_question_and_model_answer(
        db_session, exam=exam, uploader=uploader
    )
    await db_session.commit()
    await db_session.refresh(question)

    token = await _login(client, "refteacher16")
    headers = _institution_headers(token, institution.id)

    created = await client.post(
        "/api/v1/ai-reference-answers",
        json={"extracted_question_id": str(question.id)},
        headers=headers,
    )
    reference_id = created.json()["id"]
    await client.post(f"/api/v1/ai-reference-answers/{reference_id}/approve", headers=headers)

    audit_query = select(AuditLog).where(
        AuditLog.resource_type == "ai_reference_answer", AuditLog.resource_id == reference_id
    )
    audit_rows = (await db_session.execute(audit_query)).scalars().all()
    actions = {row.action for row in audit_rows}
    assert "ai_reference_answer_generation_requested" in actions
    assert "ai_reference_answer_generated" in actions
    assert "ai_reference_answer_approved" in actions


async def test_inactive_model_answer_document_never_selected_for_reference_generation(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """25. Soft-delete/inactive behavior — mirrors the equivalent
    evaluation-scoping test."""
    await create_test_user(db_session, username="refteacher15", role=seed_rbac["super_admin"])
    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="REFINACTIVE")
    uploader = await create_test_user(db_session, username="refuploader15")
    exam = await _create_exam_under(db_session, institution, code="REFINACTIVEEXAM")

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
        original_filename="ma_old.pdf",
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
        original_filename="ma_new.pdf",
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
        question_text="Explain photosynthesis.",
        final_marks=Decimal("10.00"),
        display_order=0,
        verification_status="verified",
    )
    stale_model_answer = ExtractedModelAnswer(
        institution_id=exam.institution_id,
        document_id=stale_ma_document.id,
        question_number="1",
        answer_text="The stale, superseded answer.",
        display_order=0,
        verification_status="verified",
    )
    active_model_answer = ExtractedModelAnswer(
        institution_id=exam.institution_id,
        document_id=active_ma_document.id,
        question_number="1",
        answer_text=_MODEL_ANSWER_TEXT,
        display_order=0,
        verification_status="verified",
    )
    db_session.add_all([question, stale_model_answer, active_model_answer])
    await db_session.commit()
    await db_session.refresh(question)
    await db_session.refresh(active_model_answer)

    token = await _login(client, "refteacher15")
    headers = _institution_headers(token, institution.id)

    response = await client.post(
        "/api/v1/ai-reference-answers",
        json={"extracted_question_id": str(question.id)},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["extracted_model_answer_id"] == str(active_model_answer.id)
    assert body["synthesized_reference_answer"] == _MODEL_ANSWER_TEXT
