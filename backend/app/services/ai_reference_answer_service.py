"""
ReferenceAnswerService — the AI Reference Answer Builder (see the
milestone report for the full design). `generate()` is the entry point:
given a verified `ExtractedQuestion` and its exam's verified
`ExtractedModelAnswer`, it runs the configured `AIProviderAdapter.
generate_reference()`, validates the structured result, and persists a
new, versioned `AIReferenceAnswer` row -- the official model answer is
never replaced, only expanded around (see the model's module docstring).

Reuses the exact scoping chain the Model Answer correctness milestone
established for evaluation (`ExtractedQuestion.document_id ->
OfficialExamDocument.exam_id`) to resolve the SAME exam's model-answer
document -- this builder can never accidentally pull a different exam's
model answer, for the same reason evaluation no longer can.
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
from app.models.extracted_model_answer import ExtractedModelAnswer
from app.models.extracted_question import ExtractedQuestion
from app.models.official_exam_document import OfficialExamDocument
from app.models.rubric import Rubric
from app.repositories.ai_reference_answer_repository import AIReferenceAnswerRepository
from app.schemas.ai_reference_answer import AIReferenceAnswerReject
from app.services.ai.base import ReferenceGenerationInput
from app.services.ai.exceptions import (
    AIDependencyMissingError,
    AIProviderAuthenticationError,
    AIProviderConfigurationError,
    AIProviderConnectivityError,
    AIProviderInvalidResponseError,
    AIProviderNotImplementedError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
)
from app.services.ai.registry import get_provider_adapter
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService

#: Terminal generation-failure exceptions this service catches and
#: converts into a persisted `generation_failed` row rather than letting
#: propagate uncaught (Phase 4/9: malformed/unavailable output must fail
#: safely and visibly, never silently).
_GENERATION_FAILURE_EXCEPTIONS = (
    AIProviderNotImplementedError,
    AIDependencyMissingError,
    AIProviderConfigurationError,
    AIProviderAuthenticationError,
    AIProviderConnectivityError,
    AIProviderTimeoutError,
    AIProviderRateLimitError,
    AIProviderInvalidResponseError,
)

_ACTIVE_REFERENCE_STATUSES = frozenset({"pending_verification", "approved"})


class ReferenceAnswerService(TenantScopedService[AIReferenceAnswer]):
    resource_type = "ai_reference_answer"

    def __init__(
        self,
        session: AsyncSession,
        repo: AIReferenceAnswerRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        repo = repo or AIReferenceAnswerRepository(session)
        super().__init__(session, repo, audit_service=audit_service)
        self._reference_repo = repo

    async def _resolve_provider_code(self, institution_id: uuid.UUID) -> str:
        """Identical resolution shape to `AnswerEvaluationService.
        _resolve_provider_code` (institution `AIConfiguration` -> catalog
        default -> `lexical_heuristic` fallback) — reference generation and
        evaluation deliberately share one provider-selection policy per
        institution, not two independently-configurable ones."""
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

    async def _resolve_model_answer(
        self,
        institution_id: uuid.UUID,
        question_document: OfficialExamDocument,
        question_number: str,
    ) -> ExtractedModelAnswer | None:
        """Same exam-scoped resolution the Model Answer correctness
        milestone fixed in `AnswerEvaluationService` — see that service's
        `evaluate_question()` for the full rationale. Reference generation
        must be just as immune to cross-exam contamination as evaluation."""
        document_query = (
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
        model_answer_document = (await self.session.execute(document_query)).scalars().first()
        if model_answer_document is None:
            return None

        model_answer_query = select(ExtractedModelAnswer).where(
            ExtractedModelAnswer.institution_id == institution_id,
            ExtractedModelAnswer.document_id == model_answer_document.id,
            ExtractedModelAnswer.question_number == question_number,
            ExtractedModelAnswer.deleted_at.is_(None),
        )
        return (await self.session.execute(model_answer_query)).scalars().first()

    async def generate(
        self,
        institution_id: uuid.UUID,
        extracted_question_id: uuid.UUID,
        *,
        actor_id: uuid.UUID | None,
        force: bool = False,
    ) -> AIReferenceAnswer:
        """Phase 2's pipeline end to end. Without `force`, a question that
        already has a `pending_verification`/`approved` current reference
        is a no-op returning that row (idempotent, same shape as
        `AnswerEvaluationService.evaluate_question()`); `force` always
        creates a new version (this IS `regenerate()` — see that method,
        a thin wrapper over this one)."""
        question = await self.session.get(ExtractedQuestion, extracted_question_id)
        if question is None or question.institution_id != institution_id:
            raise NotFoundError("Extracted question not found.")

        # Phase 2: must not operate on unverified official documents.
        if question.verification_status != "verified":
            raise ValidationAppError(
                "This question has not been verified yet — verify it before generating "
                "an AI reference answer."
            )

        question_document = await self.session.get(OfficialExamDocument, question.document_id)
        if question_document is None or question_document.institution_id != institution_id:
            raise NotFoundError("The official document for this question was not found.")

        model_answer = await self._resolve_model_answer(
            institution_id, question_document, question.question_number
        )
        if model_answer is None:
            raise ValidationAppError(
                "No model answer document has been uploaded for this exam yet — "
                "upload and OCR one before generating an AI reference answer."
            )
        if model_answer.verification_status != "verified":
            raise ValidationAppError(
                "The model answer for this question has not been verified yet — verify "
                "it before generating an AI reference answer."
            )

        existing = await self._reference_repo.get_current_for_question(
            institution_id, extracted_question_id
        )
        if existing is not None and not force and existing.status in _ACTIVE_REFERENCE_STATUSES:
            return existing

        max_marks = (
            question.final_marks if question.final_marks is not None else question.detected_marks
        )
        if max_marks is None:
            raise ValidationAppError(
                "This question has no maximum marks yet — verify the mark scheme before "
                "generating an AI reference answer."
            )
        marks_source = "final_marks" if question.final_marks is not None else "detected_marks"

        provider_code = await self._resolve_provider_code(institution_id)
        provider_query = select(AIProvider).where(AIProvider.code == provider_code)
        provider = (await self.session.execute(provider_query)).scalars().first()
        if provider is None:
            raise ConflictError(f"AI provider '{provider_code}' is not registered.")

        # Optional enrichment only (ADR-037's "evaluation never requires
        # this" rule extends to reference generation) — never blocks.
        rubric_text: str | None = None
        rubric_id: uuid.UUID | None = None
        if question.linked_question_id is not None:
            rubric_query = select(Rubric).where(
                Rubric.institution_id == institution_id,
                Rubric.question_id == question.linked_question_id,
                Rubric.deleted_at.is_(None),
            )
            rubric = (await self.session.execute(rubric_query)).scalars().first()
            if rubric is not None:
                rubric_id = rubric.id
                rubric_text = f"Rubric: {rubric.name} (total {rubric.total_marks} marks)"

        next_version = await self._reference_repo.get_latest_version_number(
            institution_id, extracted_question_id
        )
        reference = AIReferenceAnswer(
            institution_id=institution_id,
            extracted_question_id=extracted_question_id,
            extracted_model_answer_id=model_answer.id,
            rubric_id=rubric_id,
            ai_provider_id=provider.id,
            version=next_version + 1,
            is_current=False,  # only flipped True on a SUCCESSFUL generation, below
            status="generating",
            question_text=question.question_text,
            official_model_answer_text=model_answer.answer_text,
            maximum_marks=max_marks,
            marks_source=marks_source,
            created_by=actor_id,
        )
        self.session.add(reference)
        await self.session.flush()
        await self._log_audit(
            AuditAction.AI_REFERENCE_ANSWER_GENERATION_REQUESTED, actor_id, reference.id
        )
        await self.session.commit()

        adapter = get_provider_adapter(provider_code)
        try:
            content = adapter.generate_reference(
                ReferenceGenerationInput(
                    question_text=question.question_text,
                    official_model_answer_text=model_answer.answer_text,
                    maximum_marks=float(max_marks),
                    rubric_text=rubric_text,
                )
            )
        except _GENERATION_FAILURE_EXCEPTIONS as exc:
            # Phase 9: a failed (re)generation must never blank out a
            # previously-good current reference -- `is_current` on this
            # failed row stays False, `existing` (if any) is left alone.
            reference.status = "generation_failed"
            reference.generation_error = str(exc)
            await self.session.flush()
            await self.session.commit()
            await self._log_audit(
                AuditAction.AI_REFERENCE_ANSWER_GENERATION_FAILED, actor_id, reference.id
            )
            raise

        now = datetime.now(UTC)
        reference.status = "pending_verification"
        reference.is_current = True
        reference.synthesized_reference_answer = content.reference_answer
        reference.structured_content = {
            "required_concepts": content.required_concepts,
            "optional_concepts": content.optional_concepts,
            "keywords": content.keywords,
            "equivalent_terms": content.equivalent_terms,
            "alternative_valid_answers": content.alternative_valid_answers,
            "expected_reasoning": content.expected_reasoning,
            "common_misconceptions": content.common_misconceptions,
            "scoring_guidance": content.scoring_guidance,
        }
        reference.generation_confidence = Decimal(str(content.confidence))
        reference.has_conflict_flag = content.has_conflict_with_official_answer
        reference.conflict_notes = content.conflict_notes
        # Step 5 milestone: previously-unused columns, now populated when a
        # provider supplies them (all optional — a provider that doesn't
        # set `builder_metadata`/`grounding_report` leaves these `None`,
        # exactly as before this milestone).
        if content.builder_metadata is not None:
            reference.provider_model = content.builder_metadata.get("model_version")
            reference.prompt_version = content.builder_metadata.get("prompt_version")
        if content.grounding_report is not None or content.builder_metadata is not None:
            reference.generation_metadata = {
                "grounding_report": content.grounding_report,
                "builder_metadata": content.builder_metadata,
            }
        reference.generated_at = now
        reference.updated_by = actor_id

        if existing is not None:
            existing.is_current = False
            existing.updated_by = actor_id

        await self.session.flush()
        await self.session.refresh(reference)
        await self._log_audit(AuditAction.AI_REFERENCE_ANSWER_GENERATED, actor_id, reference.id)
        return reference

    async def regenerate(
        self,
        institution_id: uuid.UUID,
        extracted_question_id: uuid.UUID,
        *,
        actor_id: uuid.UUID | None,
    ) -> AIReferenceAnswer:
        await self._log_audit(
            AuditAction.AI_REFERENCE_ANSWER_REGENERATION_REQUESTED, actor_id, extracted_question_id
        )
        return await self.generate(
            institution_id, extracted_question_id, actor_id=actor_id, force=True
        )

    async def approve(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> AIReferenceAnswer:
        reference = await self.get_by_id(institution_id, entity_id)
        if reference.status != "pending_verification":
            raise ConflictError(
                f"Only a reference pending verification can be approved (currently "
                f"{reference.status})."
            )
        reference.status = "approved"
        reference.verified_by = actor_id
        reference.verified_at = datetime.now(UTC)
        reference.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(reference)
        await self._log_audit(AuditAction.AI_REFERENCE_ANSWER_APPROVED, actor_id, reference.id)
        return reference

    async def reject(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: AIReferenceAnswerReject,
        *,
        actor_id: uuid.UUID | None,
    ) -> AIReferenceAnswer:
        reference = await self.get_by_id(institution_id, entity_id)
        if reference.status != "pending_verification":
            raise ConflictError(
                f"Only a reference pending verification can be rejected (currently "
                f"{reference.status})."
            )
        reference.status = "rejected"
        reference.rejection_reason = data.reason
        reference.verified_by = actor_id
        reference.verified_at = datetime.now(UTC)
        # A rejected reference must never remain the one evaluation reads —
        # `AnswerEvaluationService` only ever queries for `status="approved"`
        # (see its `_resolve_approved_reference`), so this is defence in
        # depth, not the only thing preventing a rejected row from being used.
        reference.is_current = False
        reference.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(reference)
        await self._log_audit(AuditAction.AI_REFERENCE_ANSWER_REJECTED, actor_id, reference.id)
        return reference

    async def list_versions(
        self, institution_id: uuid.UUID, extracted_question_id: uuid.UUID
    ) -> list[AIReferenceAnswer]:
        return await self._reference_repo.list_versions(institution_id, extracted_question_id)

    async def get_current_for_question(
        self, institution_id: uuid.UUID, extracted_question_id: uuid.UUID
    ) -> AIReferenceAnswer | None:
        return await self._reference_repo.get_current_for_question(
            institution_id, extracted_question_id
        )
