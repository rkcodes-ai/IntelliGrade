"""Unit tests for `app.services.document_intelligence.classification` —
pure aggregation logic over `DetectedRegion` lists, no I/O."""

from app.services.document_intelligence.classification import classify_page
from app.services.document_intelligence.layout import DetectedRegion
from app.services.ocr.base import BoundingBox


def _region(region_type: str, bbox: BoundingBox, confidence: float = 90.0) -> DetectedRegion:
    return DetectedRegion(
        region_type=region_type,
        bbox=bbox,
        confidence=confidence,
        source_detector="surya_layout",
        reading_order=0,
        source_label=region_type,
    )


def test_page_dominated_by_printed_text_classifies_as_printed_text() -> None:
    regions = [_region("PRINTED_TEXT", BoundingBox(0, 0, 800, 800))]
    result = classify_page(regions)
    assert result.classification == "PRINTED_TEXT"
    assert result.used_fallback is False


def test_page_with_significant_text_and_diagram_is_mixed() -> None:
    regions = [
        _region("PRINTED_TEXT", BoundingBox(0, 0, 400, 400)),
        _region("DIAGRAM", BoundingBox(0, 400, 400, 400)),
    ]
    result = classify_page(regions)
    assert result.classification == "MIXED"


def test_tiny_stray_region_does_not_flip_the_page_classification() -> None:
    regions = [
        _region("PRINTED_TEXT", BoundingBox(0, 0, 900, 900)),
        _region("DIAGRAM", BoundingBox(0, 0, 5, 5)),  # negligible area
    ]
    result = classify_page(regions)
    assert result.classification == "PRINTED_TEXT"


def test_no_regions_falls_back_to_quality_document_type_hint() -> None:
    from app.services.document_intelligence.quality import PageQualityReport

    quality = PageQualityReport(
        quality_score=80.0,
        quality_classification="GOOD",
        blur_variance=500.0,
        blur_risk=0.0,
        skew_angle=0.0,
        orientation=0,
        contrast_score=80.0,
        brightness_mean=200.0,
        brightness_score=80.0,
        exposure="normal",
        noise_sigma=1.0,
        noise_risk=5.0,
        width_px=900,
        height_px=300,
        effective_dpi_estimate=None,
        small_text_risk=False,
        background_uniformity=90.0,
        perspective_risk=0.0,
        compression_artifact_risk=0.0,
        document_type_hint="HANDWRITTEN_DOCUMENT",
        document_type_confidence=0.7,
        recommended_operations=[],
    )
    result = classify_page([], quality=quality)
    assert result.classification == "HANDWRITTEN_TEXT"
    assert result.used_fallback is True


def test_no_regions_and_no_quality_hint_is_unknown() -> None:
    result = classify_page([])
    assert result.classification == "UNKNOWN"
    assert result.confidence == 0.0


def test_zero_area_regions_are_unknown_not_a_crash() -> None:
    regions = [_region("PRINTED_TEXT", BoundingBox(0, 0, 0, 0))]
    result = classify_page(regions)
    assert result.classification == "UNKNOWN"
