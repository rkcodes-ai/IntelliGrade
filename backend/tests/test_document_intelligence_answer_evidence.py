"""Tests for `app.services.document_intelligence.answer_evidence` — the
additive multimodal evidence assembly (Section 32/35): existing text-only
consumers must keep working, and evidence must never be flattened into
one string."""

import uuid
from types import SimpleNamespace

from app.services.document_intelligence.answer_evidence import build_answer_evidence


def _region(*, region_type: str, reading_order: int, metadata: dict | None = None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        region_type=region_type,
        bbox_left=10,
        bbox_top=20,
        bbox_width=100,
        bbox_height=50,
        confidence=85.0,
        crop_storage_key=f"regions/{region_type.lower()}.png",
        source_detector="surya_layout",
        reading_order=reading_order,
        extra_metadata=metadata,
    )


def test_build_answer_evidence_preserves_text_unchanged_for_existing_consumers() -> None:
    evidence = build_answer_evidence([], text="the raw fused OCR text")
    assert evidence.text == "the raw fused OCR text"


def test_build_answer_evidence_buckets_regions_by_type() -> None:
    regions = [
        _region(region_type="DIAGRAM", reading_order=1, metadata={"diagram_type": "flowchart"}),
        _region(region_type="EQUATION", reading_order=0, metadata={"latex": "x^2"}),
        _region(region_type="TABLE", reading_order=2, metadata={"row_count": 2}),
        _region(region_type="PRINTED_TEXT", reading_order=3),
    ]
    evidence = build_answer_evidence(regions, text="body text")

    assert len(evidence.diagram_evidence) == 1
    assert evidence.diagram_evidence[0].metadata["diagram_type"] == "flowchart"
    assert len(evidence.math_evidence) == 1
    assert evidence.math_evidence[0].metadata["latex"] == "x^2"
    assert len(evidence.table_evidence) == 1
    assert len(evidence.other_regions) == 1


def test_build_answer_evidence_orders_by_reading_order() -> None:
    regions = [
        _region(region_type="EQUATION", reading_order=5),
        _region(region_type="EQUATION", reading_order=1),
    ]
    evidence = build_answer_evidence(regions, text="")
    assert [r.bbox for r in evidence.math_evidence]  # both present, no crash on ordering


def test_build_answer_evidence_never_drops_a_region_with_failed_analysis() -> None:
    """Section 19's fallback requirement: a DIAGRAM region whose analysis
    failed (empty extra_metadata) must still appear in the evidence, not
    be silently discarded."""
    regions = [_region(region_type="DIAGRAM", reading_order=0, metadata=None)]
    evidence = build_answer_evidence(regions, text="")
    assert len(evidence.diagram_evidence) == 1
    assert evidence.diagram_evidence[0].metadata == {}


def test_has_visual_or_math_evidence_false_for_text_only() -> None:
    regions = [_region(region_type="PRINTED_TEXT", reading_order=0)]
    evidence = build_answer_evidence(regions, text="plain text page")
    assert evidence.has_visual_or_math_evidence() is False


def test_has_visual_or_math_evidence_true_when_diagram_present() -> None:
    regions = [_region(region_type="DIAGRAM", reading_order=0, metadata={})]
    evidence = build_answer_evidence(regions, text="")
    assert evidence.has_visual_or_math_evidence() is True


def test_answer_evidence_to_dict_is_json_serializable() -> None:
    import json

    regions = [
        _region(region_type="DIAGRAM", reading_order=0, metadata={"diagram_type": "flowchart"})
    ]
    evidence = build_answer_evidence(regions, text="body")
    serialized = json.dumps(evidence.to_dict())
    assert "diagram_evidence" in serialized
    assert "text" in serialized
