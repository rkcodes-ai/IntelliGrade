"""
Page/region content classification (Document Intelligence milestone,
Section 16). Per-*region* classification is already produced by
`app.services.document_intelligence.layout.detect_regions_surya()` (each
`DetectedRegion.region_type` + `confidence` IS the region-level
classification, straight from Surya's real `LayoutPredictor` — Section
16 explicitly says "prefer existing model signals + deterministic
heuristics before adding another large neural model", and Surya's output
already *is* that signal). This module adds the one thing layout
detection alone doesn't give: a **page-level aggregate** classification
(`PRINTED_TEXT`/`HANDWRITTEN_TEXT`/`DIAGRAM`/`TABLE`/`EQUATION`/`MIXED`/
`UNKNOWN`), plus a documented fallback to `PageQualityReport
.document_type_hint` when region detection produced nothing (e.g. layout
detection failed and the pipeline fell back per Section 28).

Never destroys/reroutes content on low confidence (Section 16's explicit
requirement) — this module only ever *labels*, it never drops a region.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from app.services.document_intelligence.layout import DetectedRegion
from app.services.document_intelligence.quality import DocumentTypeHint, PageQualityReport

PageContentClassification = str  # one of the values below
_TEXT_TYPES = frozenset({"PRINTED_TEXT", "HANDWRITTEN_TEXT"})
_VISUAL_TYPES = frozenset({"DIAGRAM", "TABLE", "EQUATION"})
# A region type contributes to the page-level aggregate only if it covers
# at least this fraction of the page's *classified* area — a single
# stray low-confidence region shouldn't flip the whole page's label.
_SIGNIFICANT_AREA_FRACTION = 0.05


@dataclass(frozen=True)
class PageClassificationResult:
    classification: str
    confidence: float
    region_type_area_fractions: dict[str, float]
    used_fallback: bool


def _region_area(region: DetectedRegion) -> int:
    return max(region.bbox.width, 0) * max(region.bbox.height, 0)


def classify_page(
    regions: list[DetectedRegion], *, quality: PageQualityReport | None = None
) -> PageClassificationResult:
    if not regions:
        if quality is not None and quality.document_type_hint != "UNKNOWN":
            return PageClassificationResult(
                classification=_map_document_type_hint(quality.document_type_hint),
                confidence=quality.document_type_confidence,
                region_type_area_fractions={},
                used_fallback=True,
            )
        return PageClassificationResult(
            classification="UNKNOWN",
            confidence=0.0,
            region_type_area_fractions={},
            used_fallback=True,
        )

    total_area = sum(_region_area(region) for region in regions)
    if total_area <= 0:
        return PageClassificationResult(
            classification="UNKNOWN",
            confidence=0.0,
            region_type_area_fractions={},
            used_fallback=False,
        )

    area_by_type: Counter[str] = Counter()
    for region in regions:
        area_by_type[region.region_type] += _region_area(region)

    fractions = {
        region_type: area / total_area
        for region_type, area in area_by_type.items()
        if area / total_area >= _SIGNIFICANT_AREA_FRACTION
    }

    significant_text = {t for t in fractions if t in _TEXT_TYPES}
    significant_visual = {t for t in fractions if t in _VISUAL_TYPES}
    significant_other = set(fractions) - _TEXT_TYPES - _VISUAL_TYPES

    dominant_types = significant_text | significant_visual
    if not dominant_types:
        classification = "UNKNOWN" if not significant_other else "MIXED"
    elif len(dominant_types) == 1:
        classification = next(iter(dominant_types))
    else:
        classification = "MIXED"

    # Confidence: area-weighted mean confidence of the regions that make
    # up the dominant classification (or all regions, for MIXED/UNKNOWN).
    contributing = [
        r for r in regions if classification == "MIXED" or r.region_type == classification
    ]
    if not contributing:
        contributing = regions
    weighted_confidence = sum(r.confidence * _region_area(r) for r in contributing) / max(
        sum(_region_area(r) for r in contributing), 1
    )

    return PageClassificationResult(
        classification=classification,
        confidence=weighted_confidence,
        region_type_area_fractions=fractions,
        used_fallback=False,
    )


def _map_document_type_hint(hint: DocumentTypeHint) -> str:
    return {
        "PRINTED_DOCUMENT": "PRINTED_TEXT",
        "HANDWRITTEN_DOCUMENT": "HANDWRITTEN_TEXT",
        "MIXED_DOCUMENT": "MIXED",
        "UNKNOWN": "UNKNOWN",
    }[hint]
