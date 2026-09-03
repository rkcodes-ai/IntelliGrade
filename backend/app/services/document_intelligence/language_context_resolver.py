"""
Language Context Resolver (Step 4.2 milestone, Sections 22-28).

Solves the OCR/language bootstrap problem via STAGED RESOLUTION, never a
circular dependency (Section 22): script detection is cheap and needs
no OCR text; fastText needs *some* text, which only exists after an
initial OCR pass; a configured hint (`Question.language`, when set) is
available before either. This module's `resolve_pre_ocr_context()` and
`resolve_post_ocr_context()` are the two staged entry points — never a
single function that pretends both signals are available at once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.document_intelligence.language_detection import (
    LanguageDetector,
    LanguageIdentificationResult,
)
from app.services.document_intelligence.script_detection import (
    ScriptDetectionResult,
    ScriptName,
    detect_script,
)

# A configured hint this confident wins ties against a merely-adequate
# fastText prediction (Section 37: configured language = CONTEXTUAL
# HINT, not an automatic override) -- but a HIGH-confidence, disagreeing
# detector result still surfaces as `language_disagreement=True` rather
# than being silently discarded.
_DISAGREEMENT_CONFIDENCE_THRESHOLD = 0.85


@dataclass(frozen=True)
class PreOCRContext:
    """Cheap, OCR-free evidence used to pick an initial provider set
    (Section 23) — never a fabricated claim that script/language is
    already certain."""

    configured_language_hint: str | None
    candidate_scripts: tuple[ScriptName, ...]
    provenance: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "configured_language_hint": self.configured_language_hint,
            "candidate_scripts": list(self.candidate_scripts),
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class LanguageContext:
    """Post-OCR resolved context (Section 28) — the single object
    downstream code (OCR retry decision, Step 4.1 grammar routing,
    `AnswerEvidence`) consumes."""

    primary_language: str | None
    script: ScriptName
    confidence: float
    candidate_languages: tuple[str, ...] = field(default_factory=tuple)
    is_mixed_language: bool = False
    configured_language_hint: str | None = None
    language_disagreement: bool = False
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_language": self.primary_language,
            "script": self.script,
            "confidence": self.confidence,
            "candidate_languages": list(self.candidate_languages),
            "is_mixed_language": self.is_mixed_language,
            "configured_language_hint": self.configured_language_hint,
            "language_disagreement": self.language_disagreement,
            "provenance": self.provenance,
        }


def resolve_pre_ocr_context(*, configured_language_hint: str | None = None) -> PreOCRContext:
    """Section 23/24: before any OCR runs, the only real evidence
    available is a configured hint (e.g. `Question.language`, when
    actually set to something other than the ever-present default) --
    script/language are both genuinely unknown at this point. Never
    pretends otherwise."""
    return PreOCRContext(
        configured_language_hint=configured_language_hint,
        candidate_scripts=(),
        provenance="pre_ocr_configured_hint_only",
    )


def resolve_post_ocr_context(
    ocr_text: str,
    *,
    detector: LanguageDetector,
    configured_language_hint: str | None = None,
) -> LanguageContext:
    """Section 25/28: combines real script detection + real fastText
    prediction + the configured hint into one resolved context. Never
    blindly trusts a single signal (Section 25's explicit instruction)."""
    script_result: ScriptDetectionResult = detect_script(ocr_text)
    detection_result: LanguageIdentificationResult = detector.detect(ocr_text)

    provenance: dict[str, Any] = {
        "script_detection": script_result.to_dict(),
        "language_detection": detection_result.to_dict(),
    }

    if detection_result.status in ("EMPTY_TEXT", "FAILED"):
        # Section 27/46: a detector failure must not destroy OCR evidence
        # or fabricate a language -- fall back to script-only evidence,
        # honestly reporting low/no confidence.
        return LanguageContext(
            primary_language=configured_language_hint,
            script=script_result.primary_script,
            confidence=0.0,
            candidate_languages=script_result.candidate_languages,
            is_mixed_language=script_result.is_multi_script,
            configured_language_hint=configured_language_hint,
            language_disagreement=False,
            provenance=provenance,
        )

    primary = detection_result.primary_language
    confidence = detection_result.confidence
    disagreement = False

    if (
        configured_language_hint
        and primary
        and configured_language_hint.lower() != primary.lower()
        and confidence >= _DISAGREEMENT_CONFIDENCE_THRESHOLD
    ):
        # Section 25: a high-confidence detector result that disagrees
        # with the configured hint is recorded as a genuine disagreement
        # -- the automatic result still wins (Section 37: "automatic
        # detection = PRIMARY"), the configured hint is preserved for
        # audit/reviewer-override purposes, never silently dropped.
        disagreement = True

    candidate_names = tuple(c.language for c in detection_result.candidate_languages)

    return LanguageContext(
        primary_language=primary,
        script=script_result.primary_script,
        confidence=confidence,
        candidate_languages=candidate_names or script_result.candidate_languages,
        is_mixed_language=script_result.is_multi_script,
        configured_language_hint=configured_language_hint,
        language_disagreement=disagreement,
        provenance=provenance,
    )
