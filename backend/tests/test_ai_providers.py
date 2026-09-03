"""Unit tests for the Module 06 AI evaluation provider adapter layer: the
real lexical/statistical adapter (both `evaluate()` and, since the AI
Reference Answer Builder milestone, `generate_reference()`), the two
real-but-credential-gated OpenAI/Anthropic adapters, and the
code->adapter registry."""

import pytest

from app.core.config import get_settings
from app.services.ai.base import (
    AnswerEvaluationInput,
    AnswerEvaluationResult,
    ReferenceGenerationInput,
)
from app.services.ai.exceptions import AIProviderConfigurationError
from app.services.ai.providers.anthropic_provider import AnthropicProvider
from app.services.ai.providers.lexical_heuristic_provider import LexicalHeuristicProvider
from app.services.ai.providers.openai_provider import OpenAIProvider
from app.services.ai.registry import get_provider_adapter, list_registered_codes

_QUESTION = "Explain the process of photosynthesis in plants."
_MODEL_ANSWER = (
    "Photosynthesis is the process by which green plants convert light energy "
    "into chemical energy. Chlorophyll in the leaves absorbs sunlight. Carbon "
    "dioxide and water are converted into glucose and oxygen. This occurs "
    "primarily in the chloroplasts of plant cells because light energy drives "
    "the reaction."
)


def _evaluate(student_answer_text: str, max_marks: float = 10.0) -> AnswerEvaluationResult:
    provider = LexicalHeuristicProvider()
    return provider.evaluate(
        AnswerEvaluationInput(
            question_text=_QUESTION,
            model_answer_text=_MODEL_ANSWER,
            max_marks=max_marks,
            student_answer_text=student_answer_text,
        )
    )


def test_lexical_heuristic_provider_scores_verbatim_match_near_perfect() -> None:
    result = _evaluate(_MODEL_ANSWER)

    assert result.semantic_similarity_score == 100.0
    assert result.keyword_match_score == 100.0
    assert result.concept_match_score == 100.0
    assert result.confidence_score >= 90.0
    assert result.suggested_marks == 10.0


def test_lexical_heuristic_provider_scores_good_paraphrase_moderately() -> None:
    good_answer = (
        "Photosynthesis is how green plants convert light energy into chemical "
        "energy using chlorophyll. Since sunlight is absorbed by chlorophyll, "
        "carbon dioxide and water are transformed into glucose and oxygen in the "
        "chloroplasts."
    )
    result = _evaluate(good_answer)

    assert 0.0 < result.suggested_marks < 10.0
    assert result.semantic_similarity_score > 0.0


def test_lexical_heuristic_provider_scores_poor_answer_low() -> None:
    result = _evaluate("Plants need water to grow.")

    assert result.suggested_marks < 3.0
    assert result.confidence_score < 70.0


def test_lexical_heuristic_provider_flags_irrelevant_answer_with_low_confidence() -> None:
    result = _evaluate("The stock market crashed in 1929 due to speculation.")

    assert result.relevance_score == 0.0
    assert result.confidence_score < 70.0  # forces mandatory teacher review, ADR-040


def test_lexical_heuristic_provider_handles_blank_answer_as_confident_zero() -> None:
    result = _evaluate("   ")

    assert result.suggested_marks == 0.0
    assert result.confidence_score == 100.0
    assert result.semantic_similarity_score == 0.0


def test_lexical_heuristic_provider_never_exceeds_max_marks() -> None:
    result = _evaluate(_MODEL_ANSWER, max_marks=5.0)
    assert result.suggested_marks <= 5.0


def test_lexical_heuristic_provider_generates_real_structured_reference() -> None:
    """The project's deterministic reference-generation provider — every
    automated reference-builder test exercises this, never a paid LLM
    call (Phase 13's "deterministic AI fixtures" requirement)."""
    provider = LexicalHeuristicProvider()
    content = provider.generate_reference(
        ReferenceGenerationInput(
            question_text=_QUESTION, official_model_answer_text=_MODEL_ANSWER, maximum_marks=10.0
        )
    )
    assert content.reference_answer == _MODEL_ANSWER
    assert len(content.required_concepts) > 0
    assert len(content.keywords) > 0
    # A lexical/statistical method has no way to genuinely produce these —
    # must stay honestly empty, never fabricated (see the provider's docstring).
    assert content.equivalent_terms == []
    assert content.alternative_valid_answers == []
    assert content.common_misconceptions == []
    assert 0.0 <= content.confidence <= 60.0
    assert content.has_conflict_with_official_answer is False


def test_lexical_heuristic_reference_scoring_guidance_scales_with_marks() -> None:
    """Phase 5: reference depth must respect maximum marks, not be
    hardcoded to fixed cases."""
    provider = LexicalHeuristicProvider()
    low_marks = provider.generate_reference(
        ReferenceGenerationInput(
            question_text=_QUESTION, official_model_answer_text=_MODEL_ANSWER, maximum_marks=1.0
        )
    )
    high_marks = provider.generate_reference(
        ReferenceGenerationInput(
            question_text=_QUESTION, official_model_answer_text=_MODEL_ANSWER, maximum_marks=14.0
        )
    )
    assert len(low_marks.scoring_guidance) < len(high_marks.scoring_guidance)


def test_lexical_heuristic_reference_extracts_real_reasoning_sentences() -> None:
    provider = LexicalHeuristicProvider()
    content = provider.generate_reference(
        ReferenceGenerationInput(
            question_text=_QUESTION, official_model_answer_text=_MODEL_ANSWER, maximum_marks=10.0
        )
    )
    # `_MODEL_ANSWER` contains "...because light energy drives the reaction."
    assert any("because" in sentence.lower() for sentence in content.expected_reasoning)


@pytest.mark.parametrize("provider_cls", [OpenAIProvider, AnthropicProvider])
def test_cloud_ai_providers_are_marked_implemented(provider_cls: type) -> None:
    """Real SDK-based code exists for both (see each provider's own
    module) — unlike the pre-milestone stubs, `is_implemented` is now
    `True` regardless of whether a real API key happens to be configured
    in this environment."""
    assert provider_cls().is_implemented is True


@pytest.mark.parametrize("provider_cls", [OpenAIProvider, AnthropicProvider])
def test_cloud_ai_providers_raise_configuration_error_without_credentials(
    provider_cls: type, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real, credential-gated code — this suite deliberately never
    fabricates API keys, so both `evaluate()` and `generate_reference()`
    must fail with the specific `AIProviderConfigurationError`, distinct
    from "not implemented". Cloud credentials are force-cleared so this
    holds even on a machine whose `.env` has real keys configured for
    manual verification (see the equivalent OCR test's precedent)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)

    provider = provider_cls()
    with pytest.raises(AIProviderConfigurationError):
        provider.evaluate(
            AnswerEvaluationInput(
                question_text=_QUESTION,
                model_answer_text=_MODEL_ANSWER,
                max_marks=10.0,
                student_answer_text="anything",
            )
        )
    with pytest.raises(AIProviderConfigurationError):
        provider.generate_reference(
            ReferenceGenerationInput(
                question_text=_QUESTION,
                official_model_answer_text=_MODEL_ANSWER,
                maximum_marks=10.0,
            )
        )


def test_registry_lists_all_registered_provider_codes() -> None:
    # Step 5 milestone: `local_llm_reference` was added to the registry
    # alongside the three pre-existing providers.
    assert set(list_registered_codes()) == {
        "lexical_heuristic",
        "openai",
        "anthropic",
        "local_llm_reference",
    }


def test_registry_returns_lexical_heuristic_adapter_instance() -> None:
    adapter = get_provider_adapter("lexical_heuristic")
    assert isinstance(adapter, LexicalHeuristicProvider)


def test_registry_raises_key_error_for_unknown_code() -> None:
    with pytest.raises(KeyError):
        get_provider_adapter("not-a-real-provider")
