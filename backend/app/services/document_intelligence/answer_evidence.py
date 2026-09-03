"""
Multimodal `AnswerEvidence` assembly (Step 4 milestone, Sections 30-36).

This is an ADDITIVE evaluation-interface preparation, not a scoring-engine
rewrite (Section 35): it assembles the text evidence that already exists
(unchanged, from the six-OCR ensemble/fusion) together with the
diagram/math/table evidence this milestone adds, keyed by the SAME
`DocumentRegion` rows the Document Intelligence milestone already
persists. Existing text-only consumers of `AnswerScript.structured_content`
are completely untouched by this module — nothing here modifies that
pipeline, it only reads `DocumentRegion.extra_metadata` (already populated
by `diagram_analysis`/`math_recognition`/`routing.extract_table_structure`
during OCR task processing) and regroups it per page.

Question/answer ownership (Section 30) is intentionally geometry-first
and honest about its own limits: a region is attached to the page it was
detected on, in the SAME reading order layout detection already assigned
— cross-page question-boundary association (Section 31, continuation
pages) is explicitly NOT solved here (it requires question-region
mapping this milestone doesn't have real data for) and is recorded as
future work in this milestone's final report, not silently assumed away.

**Step 4.1 addition**: `language_evidence` is an optional field, `None`
by default — every pre-Step-4.1 caller of `build_answer_evidence()`
(which didn't pass a `language_evidence` argument) gets exactly the same
object shape as before, with `language_evidence=None`. This is what
"additive, existing consumers must keep working unchanged" (Section 33
of the Language Quality milestone) means in practice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.document_region import DocumentRegion
from app.services.document_intelligence.language_quality import LanguageEvidence


@dataclass(frozen=True)
class RegionEvidence:
    """One persisted `DocumentRegion` plus its already-computed
    `extra_metadata`, re-exposed with real provenance (Section 18/38) —
    page, region id, bbox, crop location, detector, confidence."""

    region_id: str
    region_type: str
    bbox: tuple[int, int, int, int]
    confidence: float
    crop_storage_key: str | None
    source_detector: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "region_type": self.region_type,
            "bbox": self.bbox,
            "confidence": self.confidence,
            "crop_storage_key": self.crop_storage_key,
            "source_detector": self.source_detector,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class AnswerEvidence:
    """Structured, non-flattened evidence for one page (or, once assembled
    by a caller across pages, one answer) — existing text-only consumers
    keep working unchanged because `text` is exactly what they already
    receive; everything else here is new and optional to read."""

    text: str
    diagram_evidence: list[RegionEvidence] = field(default_factory=list)
    math_evidence: list[RegionEvidence] = field(default_factory=list)
    table_evidence: list[RegionEvidence] = field(default_factory=list)
    graph_evidence: list[RegionEvidence] = field(default_factory=list)
    other_regions: list[RegionEvidence] = field(default_factory=list)
    language_evidence: LanguageEvidence | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "diagram_evidence": [r.to_dict() for r in self.diagram_evidence],
            "math_evidence": [r.to_dict() for r in self.math_evidence],
            "table_evidence": [r.to_dict() for r in self.table_evidence],
            "graph_evidence": [r.to_dict() for r in self.graph_evidence],
            "other_regions": [r.to_dict() for r in self.other_regions],
            "language_evidence": self.language_evidence.to_dict()
            if self.language_evidence is not None
            else None,
        }

    def has_visual_or_math_evidence(self) -> bool:
        return bool(
            self.diagram_evidence
            or self.math_evidence
            or self.table_evidence
            or self.graph_evidence
        )


def _to_region_evidence(region: DocumentRegion) -> RegionEvidence:
    return RegionEvidence(
        region_id=str(region.id),
        region_type=region.region_type,
        bbox=(region.bbox_left, region.bbox_top, region.bbox_width, region.bbox_height),
        confidence=float(region.confidence),
        crop_storage_key=region.crop_storage_key,
        source_detector=region.source_detector,
        metadata=region.extra_metadata or {},
    )


def build_answer_evidence(
    regions: list[DocumentRegion],
    *,
    text: str,
    language_evidence: LanguageEvidence | None = None,
) -> AnswerEvidence:
    """Buckets already-persisted `DocumentRegion` rows by type — never
    re-runs analysis, never fabricates evidence for a region whose
    `extra_metadata` is still empty (e.g. a DIAGRAM region where analysis
    genuinely failed and was skipped per Section 19's fallback — it still
    appears here with an empty `metadata` dict, honestly, rather than
    being silently dropped)."""
    diagram_evidence: list[RegionEvidence] = []
    math_evidence: list[RegionEvidence] = []
    table_evidence: list[RegionEvidence] = []
    other_regions: list[RegionEvidence] = []

    for region in sorted(regions, key=lambda r: r.reading_order):
        region_evidence = _to_region_evidence(region)
        if region.region_type == "DIAGRAM":
            diagram_evidence.append(region_evidence)
        elif region.region_type == "EQUATION":
            math_evidence.append(region_evidence)
        elif region.region_type == "TABLE":
            table_evidence.append(region_evidence)
        else:
            other_regions.append(region_evidence)

    return AnswerEvidence(
        text=text,
        diagram_evidence=diagram_evidence,
        math_evidence=math_evidence,
        table_evidence=table_evidence,
        other_regions=other_regions,
        language_evidence=language_evidence,
    )
