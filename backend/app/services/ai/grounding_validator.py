"""
Grounding Validator (Step 5 milestone, Sections 40-41).

Deterministic, model-independent check for whether an AI-generated
reference claim is actually supported by the supplied official
evidence. This is the ONE place that decides "supported" — never the
same LLM being asked "are you grounded?" (Section 40's explicit
instruction: "do not rely on the same LLM simply saying 'Yes, I am
grounded.'").

Strategy (deliberately simple/explainable, not embedding similarity —
Section 40 lists that as a "later, if justified" option, not required
here): normalized token-overlap against the official evidence text.
A claim is:

- SUPPORTED: every content word in the claim appears in the evidence text
- PARTIALLY_SUPPORTED: some but not all content words appear
- UNSUPPORTED: no content words overlap with the evidence at all

This deliberately errs toward flagging things for review rather than
silently accepting fabricated detail (Section 41: "unsupported AI-
generated concepts should not become authoritative required concepts
automatically").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

GroundingStatus = Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"]

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")

# Common English function words carry no grounding signal on their own
# -- excluding them prevents a claim like "the of and" from appearing
# spuriously "supported" merely because those words appear everywhere.
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "of", "in", "on", "at", "to", "for", "and", "or", "but", "with",
        "this", "that", "these", "those", "it", "its", "as", "by", "from",
        "will", "shall", "can", "may", "must", "not", "no",
    }
)


def _content_tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN_PATTERN.findall(text)
        if token.lower() not in _STOPWORDS and len(token) > 1
    }


@dataclass(frozen=True)
class GroundingResult:
    claim: str
    status: GroundingStatus
    overlap_ratio: float
    supporting_tokens: list[str] = field(default_factory=list)
    unsupported_tokens: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "claim": self.claim,
            "status": self.status,
            "overlap_ratio": self.overlap_ratio,
            "supporting_tokens": self.supporting_tokens,
            "unsupported_tokens": self.unsupported_tokens,
        }


def validate_claim_grounding(claim: str, evidence_text: str) -> GroundingResult:
    """Real, deterministic token-overlap check — never asks a model to
    self-report. Empty claims are trivially SUPPORTED (nothing to
    fabricate); a claim with no content words after stopword removal
    (e.g. pure punctuation) is also trivially SUPPORTED for the same
    reason."""
    claim_tokens = _content_tokens(claim)
    if not claim_tokens:
        return GroundingResult(claim=claim, status="SUPPORTED", overlap_ratio=1.0)

    evidence_tokens = _content_tokens(evidence_text)
    supporting = sorted(claim_tokens & evidence_tokens)
    unsupported = sorted(claim_tokens - evidence_tokens)
    overlap_ratio = len(supporting) / len(claim_tokens)

    if overlap_ratio >= 0.999:
        status: GroundingStatus = "SUPPORTED"
    elif overlap_ratio > 0.0:
        status = "PARTIALLY_SUPPORTED"
    else:
        status = "UNSUPPORTED"

    return GroundingResult(
        claim=claim,
        status=status,
        overlap_ratio=round(overlap_ratio, 3),
        supporting_tokens=supporting,
        unsupported_tokens=unsupported,
    )


@dataclass(frozen=True)
class GroundingReport:
    """Aggregate grounding evidence for a whole generated reference —
    per-claim results plus a summary, so a caller can decide what to
    keep, downgrade, or discard (Section 41's four states are derived
    from this report by the caller, not by this module deciding marks)."""

    results: list[GroundingResult] = field(default_factory=list)

    @property
    def supported_count(self) -> int:
        return sum(1 for r in self.results if r.status == "SUPPORTED")

    @property
    def unsupported_count(self) -> int:
        return sum(1 for r in self.results if r.status == "UNSUPPORTED")

    @property
    def overall_grounding_ratio(self) -> float:
        if not self.results:
            return 1.0
        return round(sum(r.overlap_ratio for r in self.results) / len(self.results), 3)

    def unsupported_claims(self) -> list[str]:
        return [r.claim for r in self.results if r.status == "UNSUPPORTED"]

    def to_dict(self) -> dict[str, object]:
        return {
            "results": [r.to_dict() for r in self.results],
            "supported_count": self.supported_count,
            "unsupported_count": self.unsupported_count,
            "overall_grounding_ratio": self.overall_grounding_ratio,
        }


def validate_claims_grounding(claims: list[str], evidence_text: str) -> GroundingReport:
    return GroundingReport(
        results=[validate_claim_grounding(claim, evidence_text) for claim in claims]
    )
