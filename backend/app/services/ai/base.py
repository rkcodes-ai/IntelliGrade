"""
AI evaluation provider adapter interface and result shape (Module 06).

Deliberately mirrors `app.services.ocr.base`'s shape exactly (ADR-041):
every engine — real or stub — implements `AIProviderAdapter.evaluate()`
and returns the same `AnswerEvaluationResult`, regardless of what the
underlying engine looks like internally. This is what keeps
`AnswerEvaluationService` (the persistence/orchestration layer) completely
engine-agnostic, the same property Module 05's `OCRProviderAdapter` gives
the OCR pipeline.

**AI Reference Answer Builder milestone**: `generate_reference()` is added
the same way Module 12 grew `OCRProviderAdapter` — a **concrete method
with a sensible default**, not a second abstract requirement. `evaluate()`
stays the only method a provider must implement; a provider that doesn't
override `generate_reference()` gets a safe, honest default (the official
answer echoed back verbatim, no fabricated concepts/keywords, confidence
0 — never a guess dressed up as analysis).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from app.schemas.ai_reference_answer import ReferenceContentSchema


@dataclass(frozen=True)
class AnswerEvaluationInput:
    """Everything one evaluation call needs — the official model answer is
    always the primary reference input (per the brief's explicit
    requirement), not just one signal among several."""

    question_text: str
    model_answer_text: str
    max_marks: float
    student_answer_text: str
    rubric_text: str | None = None


@dataclass(frozen=True)
class AnswerEvaluationResult:
    """The 7-signal pipeline's output (ADR-039) — every component score is
    its own field, 0-100, never collapsed into one opaque number, so a
    teacher reviewing a suggestion can see which signal disagreed."""

    semantic_similarity_score: float
    keyword_match_score: float
    concept_match_score: float
    reasoning_score: float
    completeness_score: float
    relevance_score: float
    confidence_score: float
    suggested_marks: float


@dataclass(frozen=True)
class ReferenceGenerationInput:
    """Everything one reference-generation call needs. The official model
    answer is passed as `official_model_answer_text` — never optional,
    never substitutable — per the milestone's "official Model Answer
    remains authoritative" principle: a provider has nothing to expand on
    without it."""

    question_text: str
    official_model_answer_text: str
    maximum_marks: float
    rubric_text: str | None = None


class AIProviderAdapter(ABC):
    """One instance per evaluation call — adapters are stateless beyond configuration."""

    provider_code: ClassVar[str]
    is_implemented: ClassVar[bool] = False

    @abstractmethod
    def evaluate(self, data: AnswerEvaluationInput) -> AnswerEvaluationResult:
        """Run the full 7-signal evaluation pipeline for one (student
        answer x question) pair and return every component score."""
        raise NotImplementedError

    def generate_reference(self, data: ReferenceGenerationInput) -> ReferenceContentSchema:
        """Default: echo the official answer back verbatim with no
        AI-added structure — a safe, honest "nothing to add" result, not a
        fabricated one. Real providers (see
        `app.services.ai.providers.*`) override this to genuinely extract
        concepts/keywords/alternative phrasings/reasoning expectations."""
        return ReferenceContentSchema(
            reference_answer=data.official_model_answer_text,
            confidence=0.0,
        )
