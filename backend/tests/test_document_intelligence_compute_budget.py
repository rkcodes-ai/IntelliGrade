"""Tests for `app.services.document_intelligence.compute_budget` — the
eco-efficiency + resource-safety gate (Section 6/54): text-only pages
must never trigger diagram/math analysis, and per-page counts must be
capped rather than unbounded."""

from app.services.document_intelligence.compute_budget import (
    ComputeBudget,
    clamp_crop_dimensions,
    should_analyze_region,
)
from app.services.document_intelligence.layout import BoundingBox, DetectedRegion


def _region(region_type: str) -> DetectedRegion:
    return DetectedRegion(
        region_type=region_type,
        bbox=BoundingBox(left=0, top=0, width=10, height=10),
        confidence=90.0,
        source_detector="surya_layout",
        reading_order=0,
        source_label="Figure",
    )


def test_text_region_is_never_analyzed() -> None:
    assert (
        should_analyze_region(
            _region("PRINTED_TEXT"), analyzed_visual_count=0, analyzed_math_count=0
        )
        is False
    )


def test_table_region_is_never_routed_through_visual_or_math_analysis() -> None:
    """TABLE regions have their own dedicated extractor
    (`routing.extract_table_structure`) -- this gate must not also send
    them through diagram/math analysis."""
    assert (
        should_analyze_region(_region("TABLE"), analyzed_visual_count=0, analyzed_math_count=0)
        is False
    )


def test_diagram_region_is_analyzed_under_budget() -> None:
    assert (
        should_analyze_region(_region("DIAGRAM"), analyzed_visual_count=0, analyzed_math_count=0)
        is True
    )


def test_equation_region_is_analyzed_under_budget() -> None:
    assert (
        should_analyze_region(_region("EQUATION"), analyzed_visual_count=0, analyzed_math_count=0)
        is True
    )


def _gate(region, *, visual: int, math_: int, budget: ComputeBudget) -> bool:
    return should_analyze_region(
        region, analyzed_visual_count=visual, analyzed_math_count=math_, budget=budget
    )


def test_diagram_analysis_is_capped_per_page() -> None:
    budget = ComputeBudget(max_visual_regions_per_page=2)
    region = _region("DIAGRAM")
    assert _gate(region, visual=1, math_=0, budget=budget) is True
    assert _gate(region, visual=2, math_=0, budget=budget) is False


def test_math_analysis_is_capped_per_page() -> None:
    budget = ComputeBudget(max_math_regions_per_page=1)
    region = _region("EQUATION")
    assert _gate(region, visual=0, math_=0, budget=budget) is True
    assert _gate(region, visual=0, math_=1, budget=budget) is False


def test_diagram_cap_does_not_affect_math_budget_and_vice_versa() -> None:
    budget = ComputeBudget(max_visual_regions_per_page=0, max_math_regions_per_page=5)
    diagram = _region("DIAGRAM")
    equation = _region("EQUATION")
    assert _gate(diagram, visual=0, math_=0, budget=budget) is False
    assert _gate(equation, visual=0, math_=0, budget=budget) is True


def test_clamp_crop_dimensions_leaves_small_crops_untouched() -> None:
    assert clamp_crop_dimensions(400, 300) == (400, 300)


def test_clamp_crop_dimensions_downscales_oversized_crop_preserving_aspect_ratio() -> None:
    budget = ComputeBudget(max_crop_dimension_px=1000)
    width, height = clamp_crop_dimensions(4000, 2000, budget=budget)
    assert width == 1000
    assert height == 500


def test_clamp_crop_dimensions_never_upscales() -> None:
    width, height = clamp_crop_dimensions(50, 30)
    assert (width, height) == (50, 30)
