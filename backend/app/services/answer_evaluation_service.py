"""
AI evaluation orchestration (Module 06). See ADR-038/ADR-039/ADR-040.

`evaluate_question()` is the entry point: given an `ExtractedQuestion`
(from a verified Question Paper document) and an `ExamSession` (a
student's sitting), it locates the student's OCR'd answer to that
question (via `app.services.answer_extraction_service`, reading Module
05's `AnswerScript.structured_content` read-only), the matching verified
`ExtractedModelAnswer` (if any), and the mark-scheme-derived maximum, runs
the configured `AIProviderAdapter`, and writes both the current-state
`AnswerEvaluation` row and an append-only `EvaluationHistory` row (Module
04, unmodified — ADR-038).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.ai_configuration import AIConfiguration
from app.models.ai_provider import AIProvider
from app.models.ai_reference_answer import AIReferenceAnswer
from app.models.answer_evaluation import AnswerEvaluation
from app.models.answer_script import AnswerScript
from app.models.exam_result import ExamResult
from app.models.exam_session import ExamSession
from app.models.extracted_model_answer import ExtractedModelAnswer
from app.models.extracted_question import ExtractedQuestion
from app.models.official_exam_document import OfficialExamDocument
from app.repositories.answer_evaluation_repository import AnswerEvaluationRepository
from app.schemas.answer_evaluation import AnswerEvaluationOverride, AnswerEvaluationReject
from app.schemas.evaluation_history import EvaluationHistoryCreate
from app.services.ai.base import AnswerEvaluationInput
from app.services.ai.registry import get_provider_adapter
from app.services.answer_extraction_service import extract_student_answers_by_question
from app.services.audit_service import AuditService
from app.services.evaluation_history_service import EvaluationHistoryService
from app.services.tenant_service import TenantScopedService

#: ADR-040's three-band review lifecycle.
_HIGH_CONFIDENCE_THRESHOLD = Decimal("90")
_MEDIUM_CONFIDENCE_THRESHOLD = Decimal("70")

#: Once a teacher has acted on an evaluation, a plain (non-forced) trigger
#: call must not silently discard that review — see ADR-043. Only the
#: explicit `rerun()` action may recompute past this point.
_TEACHER_REVIEWED_STATUSES = frozenset(
    {"teacher_confirmed", "teacher_overridden", "teacher_rejected"}
)

#: Result lifecycle statuses (Module 07, ADR-042) past which per-question
#: evaluation edits are frozen until an explicit unlock.
_LOCKED_RESULT_STATUSES = frozenset({"locked", "published"})


def _confidence_tier(confidence_score: Decimal) -> str:
    if confidence_score >= _HIGH_CONFIDENCE_THRESHOLD:
        return "high"
    if confidence_score >= _MEDIUM_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"


def _review_status_for_tier(tier: str) -> str:
    return {"high": "auto_suggested", "medium": "pending_confirmation", "low": "pending_review"}[
        tier
    ]


class AnswerEvaluationService(TenantScopedService[AnswerEvaluation]):
    resource_type = "answer_evaluation"

    def __init__(
        self,
        session: AsyncSession,
        repo: AnswerEvaluationRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        repo = repo or AnswerEvaluationRepository(session)
        super().__init__(session, repo, audit_service=audit_service)
        self._eval_repo = repo
        self._history_service = EvaluationHistoryService(session, audit_service=self.audit_service)

    async def _resolve_provider_code(self, institution_id: uuid.UUID) -> str:
        """Institution-wide `AIConfiguration` (nullable `assessment_id`) if
        one exists, else the catalog's `is_default` provider, else the
        real implementation's own code — same resolution shape as Module
        05's `_resolve_provider_code`, generalized for AI providers."""
        config_query = select(AIConfiguration).where(
            AIConfiguration.institution_id == institution_id,
            AIConfiguration.assessment_id.is_(None),
            AIConfiguration.is_active.is_(True),
            AIConfiguration.deleted_at.is_(None),
        )
        configuration = (await self.session.execute(config_query)).scalars().first()
        if configuration is not None:
            provider = await self.session.get(AIProvider, configuration.ai_provider_id)
            if provider is not None:
                return str(provider.code)

        default_query = select(AIProvider).where(
            AIProvider.is_default.is_(True),
            AIProvider.is_enabled.is_(True),
            AIProvider.deleted_at.is_(None),
        )
        default_provider = (await self.session.execute(default_query)).scalars().first()
        if default_provider is not None:
            return str(default_provider.code)

        return "lexical_heuristic"  # last-resort fallback: always registered, always implemented

    async def _ensure_not_locked(
        self, institution_id: uuid.UUID, exam_session_id: uuid.UUID
    ) -> None:
        """Reject further evaluation writes once the parent `ExamResult`
        has reached `locked`/`published` (ADR-042) — an explicit unlock is
        required before any further per-question edit."""
        query = select(ExamResult).where(
            ExamResult.institution_id == institution_id,
            ExamResult.exam_session_id == exam_session_id,
            ExamResult.deleted_at.is_(None),
        )
        exam_result = (await self.session.execute(query)).scalars().first()
        if exam_result is not None and exam_result.status in _LOCKED_RESULT_STATUSES:
            raise ConflictError(
                f"This exam session's result is {exam_result.status} — "
                "unlock it before making further changes."
            )

    async def evaluate_question(
        self,
        institution_id: uuid.UUID,
        *,
        exam_session_id: uuid.UUID,
        extracted_question_id: uuid.UUID,
        actor_id: uuid.UUID | None,
        force: bool = False,
    ) -> AnswerEvaluation:
        """Generate (or, with `force=True`, forcibly recompute) the AI
        evaluation for one (exam session x extracted question) pair.

        Without `force`, this is the Module 06 idempotent-upsert behavior,
        unchanged, with one addition (ADR-043): once a teacher has acted
        on the row (confirm/override/reject), a plain trigger call returns
        the existing row as-is rather than silently recomputing over the
        teacher's decision — only `rerun()` (which passes `force=True`
        after snapshotting the pre-rerun state to history) may do that.
        """
        await self._ensure_not_locked(institution_id, exam_session_id)
        question = await self.session.get(ExtractedQuestion, extracted_question_id)
        if question is None or question.institution_id != institution_id:
            raise NotFoundError("Extracted question not found.")

        exam_session = await self.session.get(ExamSession, exam_session_id)
        if exam_session is None or exam_session.institution_id != institution_id:
            raise NotFoundError("Exam session not found.")

        # The question's own official document is the source of truth for
        # which `Exam` this evaluation is scoped to — cross-checked against
        # the exam session's `exam_id` so a caller can never mix a question
        # from one exam with an exam session from another (see the Model
        # Answer scoping fix below, which reuses this same `exam_id`).
        question_document = await self.session.get(OfficialExamDocument, question.document_id)
        if question_document is None or question_document.institution_id != institution_id:
            raise NotFoundError("The official document for this question was not found.")
        if question_document.exam_id != exam_session.exam_id:
            raise ValidationAppError(
                "This question belongs to a different exam than the given exam session."
            )

        max_marks = (
            question.final_marks if question.final_marks is not None else question.detected_marks
        )
        if max_marks is None:
            raise ValidationAppError(
                "This question has no maximum marks yet — verify the mark scheme before evaluating."
            )

        evaluation = await self._eval_repo.get_by_session_and_question(
            institution_id, exam_session_id, extracted_question_id
        )
        if (
            evaluation is not None
            and not force
            and evaluation.review_status in _TEACHER_REVIEWED_STATUSES
        ):
            return evaluation

        script_query = (
            select(AnswerScript)
            .where(
                AnswerScript.exam_session_id == exam_session_id,
                AnswerScript.status == "completed",
                AnswerScript.deleted_at.is_(None),
            )
            .order_by(AnswerScript.created_at.desc())
        )
        answer_script = (await self.session.execute(script_query)).scalars().first()
        if answer_script is None:
            raise NotFoundError("No completed, OCR'd answer script found for this exam session.")

        answers_by_question = extract_student_answers_by_question(
            answer_script.structured_content or {}
        )
        student_answer_text = answers_by_question.get(question.question_number, "")

        # Scoped model-answer resolution: the previous version matched
        # `ExtractedModelAnswer` by institution + `question_number` alone,
        # which could silently attach a different exam's (or even a
        # different subject's) model answer whenever two exams happened to
        # share a question number. The correct, existing relationship is
        # `ExamSession.exam_id == OfficialExamDocument.exam_id` (the same
        # `Exam` the question's own document belongs to, verified above) —
        # only an `ExtractedModelAnswer` whose `document_id` points at a
        # `document_type="model_answer"` document for THAT exam may ever be
        # selected. No new table/FK was needed; this reuses existing ones.
        model_answer_document_query = (
            select(OfficialExamDocument)
            .where(
                OfficialExamDocument.institution_id == institution_id,
                OfficialExamDocument.exam_id == question_document.exam_id,
                OfficialExamDocument.document_type == "model_answer",
                OfficialExamDocument.is_active.is_(True),
                OfficialExamDocument.deleted_at.is_(None),
            )
            .order_by(OfficialExamDocument.created_at.desc())
        )
        model_answer_document = (
            (await self.session.execute(model_answer_document_query)).scalars().first()
        )

        model_answer: ExtractedModelAnswer | None = None
        if model_answer_document is not None:
            model_answer_query = select(ExtractedModelAnswer).where(
                ExtractedModelAnswer.institution_id == institution_id,
                ExtractedModelAnswer.document_id == model_answer_document.id,
                ExtractedModelAnswer.question_number == question.question_number,
                ExtractedModelAnswer.deleted_at.is_(None),
            )
            model_answer = (await self.session.execute(model_answer_query)).scalars().first()
        model_answer_text = model_answer.answer_text if model_answer is not None else ""

        # AI Reference Answer Builder milestone (Phase 8/9): prefer an
        # APPROVED reference over the raw model answer text whenever one
        # exists for this question — the official model answer is never
        # replaced (the reference is itself built FROM it, see
        # `ReferenceAnswerService.generate`), just given richer, AI-
        # structured context to evaluate against. `used_legacy_reference`
        # is the explicit, visible, deterministic Phase 9 fallback marker:
        # `True` whenever no approved reference existed at evaluation
        # time (not yet generated, generation failed, or still pending
        # verification) — never a silent substitution either way.
        reference_query = select(AIReferenceAnswer).where(
            AIReferenceAnswer.institution_id == institution_id,
            AIReferenceAnswer.extracted_question_id == extracted_question_id,
            AIReferenceAnswer.is_current.is_(True),
            AIReferenceAnswer.status == "approved",
            AIReferenceAnswer.deleted_at.is_(None),
        )
        reference = (await self.session.execute(reference_query)).scalars().first()
        used_legacy_reference = reference is None
        evaluation_reference_text = model_answer_text
        rubric_text: str | None = None
        if reference is not None and reference.synthesized_reference_answer:
            evaluation_reference_text = reference.synthesized_reference_answer
            structured = reference.structured_content or {}
            guidance_parts = [
                *structured.get("required_concepts", []),
                *structured.get("scoring_guidance", []),
            ]
            rubric_text = "; ".join(guidance_parts) if guidance_parts else None

        provider_code = await self._resolve_provider_code(institution_id)
        provider_query = select(AIProvider).where(AIProvider.code == provider_code)
        provider = (await self.session.execute(provider_query)).scalars().first()
        if provider is None:
            raise ConflictError(f"AI provider '{provider_code}' is not registered.")

        adapter = get_provider_adapter(provider_code)
        result = adapter.evaluate(
            AnswerEvaluationInput(
                question_text=question.question_text,
                model_answer_text=evaluation_reference_text,
                max_marks=float(max_marks),
                student_answer_text=student_answer_text,
                rubric_text=rubric_text,
            )
        )

        confidence_score = Decimal(str(result.confidence_score))
        tier = _confidence_tier(confidence_score)
        review_status = _review_status_for_tier(tier)
        suggested_marks = Decimal(str(result.suggested_marks))
        now = datetime.now(UTC)

        if evaluation is None:
            evaluation = AnswerEvaluation(
                institution_id=institution_id,
                exam_session_id=exam_session_id,
                answer_script_id=answer_script.id,
                extracted_question_id=extracted_question_id,
                max_marks=max_marks,
                created_by=actor_id,
            )
            self.session.add(evaluation)

        evaluation.extracted_model_answer_id = model_answer.id if model_answer is not None else None
        evaluation.ai_reference_answer_id = reference.id if reference is not None else None
        evaluation.used_legacy_reference = used_legacy_reference
        evaluation.ai_provider_id = provider.id
        evaluation.student_answer_text = student_answer_text
        evaluation.semantic_similarity_score = Decimal(str(result.semantic_similarity_score))
        evaluation.keyword_match_score = Decimal(str(result.keyword_match_score))
        evaluation.concept_match_score = Decimal(str(result.concept_match_score))
        evaluation.reasoning_score = Decimal(str(result.reasoning_score))
        evaluation.completeness_score = Decimal(str(result.completeness_score))
        evaluation.relevance_score = Decimal(str(result.relevance_score))
        evaluation.confidence_score = confidence_score
        evaluation.confidence_tier = tier
        evaluation.max_marks = max_marks
        evaluation.suggested_marks = suggested_marks
        evaluation.review_status = review_status
        evaluation.evaluated_at = now
        # High confidence still leaves room for a teacher override later
        # (ADR-040) — auto-populating final_marks here is a convenience,
        # not a lock; `review_status` still allows `override()` to change it.
        evaluation.final_marks = suggested_marks if tier == "high" else None
        evaluation.notes = None
        evaluation.reviewed_by = None
        evaluation.reviewed_at = None
        evaluation.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(evaluation)

        await self._history_service.create(
            institution_id,
            EvaluationHistoryCreate(
                exam_session_id=exam_session_id,
                answer_key_id=(
                    model_answer.linked_answer_key_id if model_answer is not None else None
                ),
                evaluator_type="ai",
                score=suggested_marks,
                confidence_score=(confidence_score / Decimal("100")).quantize(Decimal("0.001")),
                notes=(
                    f"AI evaluation via '{provider_code}' for question {question.question_number}."
                ),
            ),
            created_by=actor_id,
        )
        await self._log_audit(AuditAction.ANSWER_EVALUATION_GENERATED, actor_id, evaluation.id)
        return evaluation

    async def confirm(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> AnswerEvaluation:
        evaluation = await self.get_by_id(institution_id, entity_id)
        await self._ensure_not_locked(institution_id, evaluation.exam_session_id)
        if evaluation.suggested_marks is None:
            raise ConflictError("This evaluation has no suggested marks to confirm.")
        evaluation.final_marks = evaluation.suggested_marks
        evaluation.review_status = "teacher_confirmed"
        evaluation.reviewed_by = actor_id
        evaluation.reviewed_at = datetime.now(UTC)
        evaluation.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(evaluation)
        await self._record_review_history(institution_id, evaluation, actor_id)
        await self._log_audit(AuditAction.ANSWER_EVALUATION_CONFIRMED, actor_id, evaluation.id)
        return evaluation

    async def override(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: AnswerEvaluationOverride,
        *,
        actor_id: uuid.UUID | None,
    ) -> AnswerEvaluation:
        evaluation = await self.get_by_id(institution_id, entity_id)
        await self._ensure_not_locked(institution_id, evaluation.exam_session_id)
        if data.final_marks > evaluation.max_marks:
            raise ValidationAppError(
                f"Override marks ({data.final_marks}) exceed this question's "
                f"maximum ({evaluation.max_marks})."
            )
        evaluation.final_marks = data.final_marks
        evaluation.notes = data.notes
        evaluation.review_status = "teacher_overridden"
        evaluation.reviewed_by = actor_id
        evaluation.reviewed_at = datetime.now(UTC)
        evaluation.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(evaluation)
        await self._record_review_history(institution_id, evaluation, actor_id)
        await self._log_audit(AuditAction.ANSWER_EVALUATION_OVERRIDDEN, actor_id, evaluation.id)
        return evaluation

    async def reject(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: AnswerEvaluationReject,
        *,
        actor_id: uuid.UUID | None,
    ) -> AnswerEvaluation:
        """Teacher Review action (Module 07, ADR-043): discard this AI
        evaluation entirely. `suggested_marks` (the original AI marks) is
        left untouched — only `final_marks` is cleared — so the AI's
        original suggestion remains visible/inspectable even after
        rejection, same "never overwrite AI values" rule as `override()`.
        """
        evaluation = await self.get_by_id(institution_id, entity_id)
        await self._ensure_not_locked(institution_id, evaluation.exam_session_id)
        evaluation.final_marks = None
        evaluation.notes = data.reason
        evaluation.review_status = "teacher_rejected"
        evaluation.reviewed_by = actor_id
        evaluation.reviewed_at = datetime.now(UTC)
        evaluation.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(evaluation)
        await self._record_review_history(institution_id, evaluation, actor_id)
        await self._log_audit(AuditAction.ANSWER_EVALUATION_REJECTED, actor_id, evaluation.id)
        return evaluation

    async def rerun(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> AnswerEvaluation:
        """Teacher Review action (Module 07, ADR-043): force a fresh AI
        evaluation even over an already-reviewed row. The pre-rerun state
        is written to `EvaluationHistory` first — a rerun is never a
        silent, unrecoverable overwrite."""
        evaluation = await self.get_by_id(institution_id, entity_id)
        await self._ensure_not_locked(institution_id, evaluation.exam_session_id)
        confidence_fraction = (
            (evaluation.confidence_score / Decimal("100")).quantize(Decimal("0.001"))
            if evaluation.confidence_score is not None
            else None
        )
        await self._history_service.create(
            institution_id,
            EvaluationHistoryCreate(
                exam_session_id=evaluation.exam_session_id,
                evaluator_type="human",
                evaluator_user_id=actor_id,
                score=evaluation.final_marks,
                confidence_score=confidence_fraction,
                notes=(
                    f"Pre-rerun snapshot (review_status was "
                    f"{evaluation.review_status!r}) before a forced AI re-evaluation."
                ),
            ),
            created_by=actor_id,
        )
        updated = await self.evaluate_question(
            institution_id,
            exam_session_id=evaluation.exam_session_id,
            extracted_question_id=evaluation.extracted_question_id,
            actor_id=actor_id,
            force=True,
        )
        await self._log_audit(AuditAction.ANSWER_EVALUATION_RERUN, actor_id, updated.id)
        return updated

    async def _record_review_history(
        self, institution_id: uuid.UUID, evaluation: AnswerEvaluation, actor_id: uuid.UUID | None
    ) -> None:
        confidence_fraction = (
            (evaluation.confidence_score / Decimal("100")).quantize(Decimal("0.001"))
            if evaluation.confidence_score is not None
            else None
        )
        await self._history_service.create(
            institution_id,
            EvaluationHistoryCreate(
                exam_session_id=evaluation.exam_session_id,
                evaluator_type="human",
                evaluator_user_id=actor_id,
                score=evaluation.final_marks,
                confidence_score=confidence_fraction,
                notes=f"Teacher review: {evaluation.review_status}.",
            ),
            created_by=actor_id,
        )
