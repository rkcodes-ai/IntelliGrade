"""Unit tests for `app.services.document_intelligence.enhancement` —
plan-building is pure/deterministic; `enhance_page()` is tested against
the actual `image_processing` step functions it wraps."""

import cv2
import numpy as np

from app.services.document_intelligence.enhancement import build_enhancement_plan, enhance_page
from app.services.document_intelligence.quality import analyze_page_quality

_FONT = cv2.FONT_HERSHEY_SIMPLEX


def _clean_text_page(height: int = 300, width: int = 900) -> np.ndarray:
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    cv2.putText(image, "Sample text line one", (20, 60), _FONT, 1.0, (0, 0, 0), 2)
    cv2.putText(image, "Sample text line two", (20, 140), _FONT, 1.0, (0, 0, 0), 2)
    return image


def test_clean_page_produces_empty_plan_and_is_returned_unchanged() -> None:
    image = _clean_text_page()
    quality = analyze_page_quality(image)
    plan, profile = build_enhancement_plan(quality)
    assert plan == []
    assert profile == "printed"

    result = enhance_page(image, quality)
    assert result.operations_applied == []
    assert result.image is image  # true fast path: same object, no copy


def test_skewed_page_gets_a_deskew_plan_and_visibly_different_output() -> None:
    image = _clean_text_page()
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width // 2, height // 2), 6.0, 1.0)
    skewed = cv2.warpAffine(image, matrix, (width, height), borderValue=(255, 255, 255))

    quality = analyze_page_quality(skewed)
    result = enhance_page(skewed, quality)
    assert "deskew" in result.operations_applied
    assert result.image is not skewed


def test_handwritten_profile_downgrades_denoise_and_skips_background_clean() -> None:
    """Section 10: handwriting-safe profile must not run background_clean
    (morphological, can erase thin strokes) even when quality signals
    would otherwise recommend it."""
    from app.services.document_intelligence.quality import PageQualityReport

    quality = PageQualityReport(
        quality_score=50.0,
        quality_classification="FAIR",
        blur_variance=500.0,
        blur_risk=0.0,
        skew_angle=0.0,
        orientation=0,
        contrast_score=80.0,
        brightness_mean=200.0,
        brightness_score=80.0,
        exposure="normal",
        noise_sigma=8.0,
        noise_risk=60.0,
        width_px=900,
        height_px=300,
        effective_dpi_estimate=None,
        small_text_risk=False,
        background_uniformity=50.0,
        perspective_risk=0.0,
        compression_artifact_risk=0.0,
        document_type_hint="HANDWRITTEN_DOCUMENT",
        document_type_confidence=0.8,
        recommended_operations=["background_clean", "denoise"],
    )
    plan, profile = build_enhancement_plan(quality)
    assert profile == "handwritten"
    assert "background_clean" not in plan
    assert "denoise" in plan  # downgraded strength, not skipped entirely


def test_diagram_risk_forces_diagram_safe_profile() -> None:
    from app.services.document_intelligence.quality import PageQualityReport

    quality = PageQualityReport(
        quality_score=60.0,
        quality_classification="FAIR",
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
        background_uniformity=50.0,
        perspective_risk=0.0,
        compression_artifact_risk=0.0,
        document_type_hint="PRINTED_DOCUMENT",
        document_type_confidence=0.8,
        recommended_operations=["background_clean"],
    )
    plan, profile = build_enhancement_plan(quality, has_diagram_risk=True)
    assert profile == "diagram_safe"
    assert "background_clean" not in plan


def test_plan_ordering_is_geometry_before_tone() -> None:
    from app.services.document_intelligence.quality import PageQualityReport

    quality = PageQualityReport(
        quality_score=40.0,
        quality_classification="POOR",
        blur_variance=500.0,
        blur_risk=0.0,
        skew_angle=3.0,
        orientation=0,
        contrast_score=40.0,
        brightness_mean=200.0,
        brightness_score=80.0,
        exposure="normal",
        noise_sigma=1.0,
        noise_risk=5.0,
        width_px=900,
        height_px=300,
        effective_dpi_estimate=None,
        small_text_risk=False,
        background_uniformity=50.0,
        perspective_risk=0.0,
        compression_artifact_risk=0.0,
        document_type_hint="PRINTED_DOCUMENT",
        document_type_confidence=0.8,
        recommended_operations=["contrast", "deskew"],
    )
    plan, _profile = build_enhancement_plan(quality)
    assert plan.index("deskew") < plan.index("contrast")
