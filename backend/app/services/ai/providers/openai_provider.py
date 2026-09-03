"""
Real AI adapter wrapping OpenAI's Chat Completions API. Credential-gated,
same honesty standard as Module 12's OCR cloud providers (Azure/Google/
AWS): real SDK-based code, genuinely runnable once `OPENAI_API_KEY` is
configured, but **not runtime-verified against a live OpenAI account** in
this environment — never fabricated credentials, never a live paid call
from automated tests (see `LexicalHeuristicProvider`, the deterministic
provider all automated tests actually exercise).

Both `evaluate()` and `generate_reference()` request `response_format=
{"type": "json_object"}` (OpenAI's native structured-JSON mode) and
validate the parsed JSON against this project's own schemas
(`AnswerEvaluationResult`/`ReferenceContentSchema`) before returning —
malformed/unparseable output raises `AIProviderInvalidResponseError`
(Phase 4), never a guessed or partially-filled result.
"""

import json
from typing import TYPE_CHECKING, Any

from app.core.config import get_settings
from app.schemas.ai_reference_answer import ReferenceContentSchema
from app.services.ai.base import (
    AIProviderAdapter,
    AnswerEvaluationInput,
    AnswerEvaluationResult,
    ReferenceGenerationInput,
)
from app.services.ai.exceptions import (
    AIDependencyMissingError,
    AIProviderAuthenticationError,
    AIProviderConfigurationError,
    AIProviderConnectivityError,
    AIProviderInvalidResponseError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
)

if TYPE_CHECKING:
    from openai import OpenAI

settings = get_settings()

_EVALUATION_SYSTEM_PROMPT = (
    "You are an exam answer grader. Compare the student's answer to the official "
    "model answer for the given question and score it on six 0-100 signals: "
    "semantic_similarity_score, keyword_match_score, concept_match_score, "
    "reasoning_score, completeness_score, relevance_score. Also return an overall "
    "confidence_score (0-100) and suggested_marks (0 to max_marks). "
    "Respond ONLY as a JSON object with exactly these keys: "
    '{"semantic_similarity_score": number, "keyword_match_score": number, '
    '"concept_match_score": number, "reasoning_score": number, '
    '"completeness_score": number, "relevance_score": number, '
    '"confidence_score": number, "suggested_marks": number}.'
)

_REFERENCE_SYSTEM_PROMPT = (
    "You are an exam-preparation assistant building a grading reference from an "
    "official, authoritative model answer. The official answer is always correct "
    "and must never be contradicted or replaced -- you may only expand, clarify, "
    "and structure it: extract required/optional concepts, keywords, equivalent "
    "terminology, alternative valid phrasings, expected reasoning steps, common "
    "misconceptions, and mark-aware scoring guidance proportional to the question's "
    "maximum marks. If anything you would generate conflicts with the official "
    "answer, set has_conflict_with_official_answer=true and explain in "
    "conflict_notes instead of silently overriding it. "
    "Respond ONLY as a JSON object with exactly these keys: "
    '{"reference_answer": string, "required_concepts": [string], '
    '"optional_concepts": [string], "keywords": [string], '
    '"equivalent_terms": [string], "alternative_valid_answers": [string], '
    '"expected_reasoning": [string], "common_misconceptions": [string], '
    '"scoring_guidance": [string], "confidence": number, '
    '"has_conflict_with_official_answer": boolean, "conflict_notes": string|null}.'
)


class OpenAIProvider(AIProviderAdapter):
    provider_code = "openai"
    is_implemented = True

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL
        self._client: OpenAI | None = None

    def _get_client(self) -> "OpenAI":
        if not self.api_key:
            raise AIProviderConfigurationError(
                "OPENAI_API_KEY is not configured. Set it to activate this provider, "
                "or select a different one."
            )
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except Exception as exc:  # noqa: BLE001 - covers native/import failures too
            raise AIDependencyMissingError(
                "The 'openai' package is not installed in this environment. Install "
                "it to activate this provider, or select a different one."
            ) from exc
        self._client = OpenAI(api_key=self.api_key)
        return self._client

    def _chat_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        client = self._get_client()
        from openai import (
            APIConnectionError,
            APITimeoutError,
            AuthenticationError,
            RateLimitError,
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
        except AuthenticationError as exc:
            raise AIProviderAuthenticationError(f"OpenAI rejected the API key: {exc}") from exc
        except RateLimitError as exc:
            raise AIProviderRateLimitError(f"OpenAI rate limit exceeded: {exc}") from exc
        except APITimeoutError as exc:
            raise AIProviderTimeoutError(f"OpenAI request timed out: {exc}") from exc
        except APIConnectionError as exc:
            raise AIProviderConnectivityError(f"Could not reach OpenAI: {exc}") from exc

        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise AIProviderInvalidResponseError("OpenAI returned an empty response.")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AIProviderInvalidResponseError(
                f"OpenAI returned non-JSON content: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise AIProviderInvalidResponseError("OpenAI's JSON response was not an object.")
        return parsed

    def evaluate(self, data: AnswerEvaluationInput) -> AnswerEvaluationResult:
        user_prompt = (
            f"Question: {data.question_text}\n\n"
            f"Official model answer: {data.model_answer_text}\n\n"
            f"Maximum marks: {data.max_marks}\n\n"
            f"Student's answer: {data.student_answer_text}"
        )
        parsed = self._chat_json(system_prompt=_EVALUATION_SYSTEM_PROMPT, user_prompt=user_prompt)
        try:
            return AnswerEvaluationResult(
                semantic_similarity_score=float(parsed["semantic_similarity_score"]),
                keyword_match_score=float(parsed["keyword_match_score"]),
                concept_match_score=float(parsed["concept_match_score"]),
                reasoning_score=float(parsed["reasoning_score"]),
                completeness_score=float(parsed["completeness_score"]),
                relevance_score=float(parsed["relevance_score"]),
                confidence_score=float(parsed["confidence_score"]),
                suggested_marks=float(parsed["suggested_marks"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AIProviderInvalidResponseError(
                f"OpenAI's JSON response was missing/invalid fields: {exc}"
            ) from exc

    def generate_reference(self, data: ReferenceGenerationInput) -> ReferenceContentSchema:
        user_prompt = (
            f"Question: {data.question_text}\n\n"
            f"Official model answer: {data.official_model_answer_text}\n\n"
            f"Maximum marks: {data.maximum_marks}"
        )
        if data.rubric_text:
            user_prompt += f"\n\nRubric: {data.rubric_text}"
        parsed = self._chat_json(system_prompt=_REFERENCE_SYSTEM_PROMPT, user_prompt=user_prompt)
        try:
            return ReferenceContentSchema.model_validate(parsed)
        except Exception as exc:  # noqa: BLE001 - pydantic.ValidationError, any shape mismatch
            raise AIProviderInvalidResponseError(
                f"OpenAI's JSON response did not match the reference schema: {exc}"
            ) from exc
