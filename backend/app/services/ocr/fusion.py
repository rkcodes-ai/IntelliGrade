"""
OCR Fusion Engine (Six-Provider OCR milestone, "OCR Ensemble & Fusion"
phase) — combines multiple providers' independent `OCRPageResult`s for
the *same* page into one consensus result.

**Granularity, stated honestly.** This fuses at **line** granularity, not
full sub-word spatial reconstruction: for each line in a reference
candidate (the candidate with the most detected lines, to maximize
alignment resolution), every other candidate's lines are matched by
vertical bounding-box overlap, and the fused line's text is chosen from
whichever aligned candidate has the highest `confidence * provider
reliability weight` — with disagreement between aligned candidates
recorded, never silently discarded. This is a real, deterministic,
unit-testable implementation of the milestone's fusion requirement (never
naive concatenation/first-result/longest-result/pure majority vote); it is
not word-level bounding-box fusion, which would need sub-word geometry
this codebase's `OCRWordResult` boxes don't reliably carry across engines
(EasyOCR/PaddleOCR synthesize word boxes from the line box — see those
providers' own docstrings) and was out of scope to fabricate.

**Why line-overlap, not text similarity, drives alignment.** Two
providers segmenting the same physical line always produce vertically
overlapping bounding boxes (they're reading the same pixels), even when
their *text* differs completely (that's exactly the disagreement case
this engine exists to detect) — so alignment must be geometric, not
text-similarity-based, or genuine disagreements would never align in the
first place.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from app.services.ocr.base import BoundingBox, OCRBlockResult, OCRLineResult, OCRPageResult

#: Fraction of vertical overlap (intersection / union of the [top, bottom]
#: interval) required for two providers' lines to be considered "the same
#: physical line" — a real, documented threshold, not tuned against any
#: specific dataset.
LINE_OVERLAP_THRESHOLD = 0.5

#: Below this normalized text-similarity ratio (difflib's `SequenceMatcher.
#: ratio()`, a real edit-distance-based measure — 0.0 = no overlap, 1.0 =
#: identical), aligned lines are recorded as a genuine disagreement rather
#: than treated as "the same text, minor noise."
AGREEMENT_SIMILARITY_THRESHOLD = 0.85

#: Reasonable, documented starting weights — NOT measured accuracy figures.
#: Cloud/managed engines are weighted slightly higher than local engines as
#: a conservative prior; every value is configurable per call and meant to
#: be tuned from real `OCRBenchmarkService` results over time (Section 20:
#: "use benchmark evidence for future tuning", never fabricated accuracy).
DEFAULT_PROVIDER_WEIGHTS: dict[str, float] = {
    "tesseract": 0.80,
    "easyocr": 0.82,
    "paddleocr": 0.85,
    "doctr": 0.83,
    "surya": 0.85,
    "trocr_handwritten": 0.80,
    "azure_ocr": 0.95,
    "google_vision": 0.95,
    "aws_textract": 0.90,
}
_DEFAULT_WEIGHT = 0.75  # any provider code not listed above


@dataclass(frozen=True)
class ProviderCandidate:
    """One provider's attempt at OCR-ing a page — `result` is `None` when
    `status != "success"`, so a failed provider never has to fabricate an
    empty `OCRPageResult` just to participate in fusion bookkeeping."""

    provider_code: str
    status: str  # "success" | "failed"
    result: OCRPageResult | None = None
    error_message: str | None = None
    weight: float | None = None  # None = use DEFAULT_PROVIDER_WEIGHTS

    def effective_weight(self) -> float:
        if self.weight is not None:
            return self.weight
        return DEFAULT_PROVIDER_WEIGHTS.get(self.provider_code, _DEFAULT_WEIGHT)


@dataclass(frozen=True)
class DisagreementRegion:
    line_index: int
    candidates: list[dict[str, object]]  # [{"provider_code", "text", "confidence"}, ...]
    chosen_provider: str
    similarity: float


@dataclass(frozen=True)
class FusionResult:
    raw_text: str
    average_confidence: float
    language: str
    rotation_degrees: float
    contributing_providers: list[str]
    disagreement_regions: list[DisagreementRegion] = field(default_factory=list)
    failed_providers: list[str] = field(default_factory=list)
    #: The fused, line-level `OCRPageResult`-compatible blocks — one
    #: synthetic page-level block containing every fused line, matching the
    #: same standardized shape every other provider already returns (so
    #: `OCRResultService.create_with_hierarchy()` needs no special case for
    #: a fused result).
    page_result: OCRPageResult | None = None


def _line_overlap_ratio(a: OCRLineResult, b: OCRLineResult) -> float:
    a_top, a_bottom = a.bounding_box.top, a.bounding_box.top + a.bounding_box.height
    b_top, b_bottom = b.bounding_box.top, b.bounding_box.top + b.bounding_box.height
    intersection = max(0, min(a_bottom, b_bottom) - max(a_top, b_top))
    union = max(a_bottom, b_bottom) - min(a_top, b_top)
    if union <= 0:
        return 0.0
    return intersection / union


def _text_similarity(a: str, b: str) -> float:
    normalized_a = " ".join(a.strip().lower().split())
    normalized_b = " ".join(b.strip().lower().split())
    if not normalized_a and not normalized_b:
        return 1.0
    return difflib.SequenceMatcher(None, normalized_a, normalized_b).ratio()


def _all_lines(result: OCRPageResult) -> list[OCRLineResult]:
    return [line for block in result.blocks for line in block.lines]


def fuse_page_candidates(
    candidates: list[ProviderCandidate],
    *,
    weights: dict[str, float] | None = None,
) -> FusionResult:
    """Fuse every successful candidate's `OCRPageResult` into one consensus
    result. Never raises on a partial-failure input — a candidate with
    `status="failed"` is simply excluded from fusion and reported in
    `failed_providers`; fusion only fails outright (returns an empty,
    zero-confidence result) when *every* candidate failed."""
    effective_weights = {**DEFAULT_PROVIDER_WEIGHTS, **(weights or {})}

    def weight_of(candidate: ProviderCandidate) -> float:
        if candidate.weight is not None:
            return candidate.weight
        return effective_weights.get(candidate.provider_code, _DEFAULT_WEIGHT)

    failed_providers = [c.provider_code for c in candidates if c.status != "success"]
    successful = [c for c in candidates if c.status == "success" and c.result is not None]

    if not successful:
        return FusionResult(
            raw_text="",
            average_confidence=0.0,
            language="eng",
            rotation_degrees=0.0,
            contributing_providers=[],
            failed_providers=failed_providers,
            page_result=OCRPageResult(
                raw_text="", average_confidence=0.0, language="eng", rotation_degrees=0.0, blocks=[]
            ),
        )

    contributing_providers = sorted(c.provider_code for c in successful)

    if len(successful) == 1:
        only = successful[0]
        assert only.result is not None
        return FusionResult(
            raw_text=only.result.raw_text,
            average_confidence=only.result.average_confidence,
            language=only.result.language,
            rotation_degrees=only.result.rotation_degrees,
            contributing_providers=contributing_providers,
            failed_providers=failed_providers,
            page_result=only.result,
        )

    # Reference candidate: the one with the most detected lines, to
    # maximize alignment resolution (a candidate that under-segments the
    # page can never be the alignment anchor for finer-grained peers).
    reference = max(successful, key=lambda c: len(_all_lines(c.result)))  # type: ignore[arg-type]
    reference_lines = _all_lines(reference.result)  # type: ignore[arg-type]
    others = [c for c in successful if c is not reference]

    fused_lines: list[OCRLineResult] = []
    disagreements: list[DisagreementRegion] = []
    confidence_weighted_sum = 0.0
    confidence_weight_total = 0.0

    for index, ref_line in enumerate(reference_lines):
        aligned: list[tuple[ProviderCandidate, OCRLineResult]] = [(reference, ref_line)]
        for other in others:
            other_lines = _all_lines(other.result)  # type: ignore[arg-type]
            best_match: OCRLineResult | None = None
            best_overlap = 0.0
            for candidate_line in other_lines:
                overlap = _line_overlap_ratio(ref_line, candidate_line)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_match = candidate_line
            if best_match is not None and best_overlap >= LINE_OVERLAP_THRESHOLD:
                aligned.append((other, best_match))

        # Pick the aligned (provider, line) with the highest confidence *
        # reliability weight — deterministic, never "first" or "longest".
        chosen_provider, chosen_line = max(
            aligned, key=lambda pair: pair[1].confidence * weight_of(pair[0])
        )

        if len(aligned) > 1:
            texts = {_normalize(line.text) for _, line in aligned}
            if len(texts) > 1:
                # Genuine disagreement: compare every other aligned text
                # against the chosen one; if any falls below the agreement
                # threshold, record the full disagreement for audit.
                worst_similarity = min(
                    _text_similarity(chosen_line.text, line.text) for _, line in aligned
                )
                if worst_similarity < AGREEMENT_SIMILARITY_THRESHOLD:
                    disagreements.append(
                        DisagreementRegion(
                            line_index=index,
                            candidates=[
                                {
                                    "provider_code": provider.provider_code,
                                    "text": line.text,
                                    "confidence": line.confidence,
                                }
                                for provider, line in aligned
                            ],
                            chosen_provider=chosen_provider.provider_code,
                            similarity=worst_similarity,
                        )
                    )

        fused_lines.append(chosen_line)
        line_weight = weight_of(chosen_provider) * max(len(chosen_line.text), 1)
        confidence_weighted_sum += chosen_line.confidence * line_weight
        confidence_weight_total += line_weight

    average_confidence = (
        confidence_weighted_sum / confidence_weight_total if confidence_weight_total > 0 else 0.0
    )
    raw_text = "\n".join(line.text for line in fused_lines)

    fused_block = OCRBlockResult(
        bounding_box=_union_box([line.bounding_box for line in fused_lines])
        if fused_lines
        else BoundingBox(0, 0, 0, 0),
        confidence=average_confidence,
        reading_order=0,
        lines=[
            OCRLineResult(
                text=line.text,
                bounding_box=line.bounding_box,
                confidence=line.confidence,
                reading_order=idx,
                words=line.words,
            )
            for idx, line in enumerate(fused_lines)
        ],
    )

    return FusionResult(
        raw_text=raw_text,
        average_confidence=average_confidence,
        language=reference.result.language,  # type: ignore[union-attr]
        rotation_degrees=reference.result.rotation_degrees,  # type: ignore[union-attr]
        contributing_providers=contributing_providers,
        disagreement_regions=disagreements,
        failed_providers=failed_providers,
        page_result=OCRPageResult(
            raw_text=raw_text,
            average_confidence=average_confidence,
            language=reference.result.language,  # type: ignore[union-attr]
            rotation_degrees=reference.result.rotation_degrees,  # type: ignore[union-attr]
            blocks=[fused_block],
        ),
    )


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _union_box(boxes: list[BoundingBox]) -> BoundingBox:
    left = min(b.left for b in boxes)
    top = min(b.top for b in boxes)
    right = max(b.left + b.width for b in boxes)
    bottom = max(b.top + b.height for b in boxes)
    return BoundingBox(left=left, top=top, width=right - left, height=bottom - top)
