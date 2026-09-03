"""Unit tests for `app.services.document_intelligence.quality` — every
metric is deterministic pixel math, so these are fast, dependency-free
tests using synthetic in-memory images (no real document samples needed)."""

import cv2
import numpy as np
import pytest

from app.services.document_intelligence.quality import analyze_page_quality

_FONT = cv2.FONT_HERSHEY_SIMPLEX


def _clean_text_page(height: int = 300, width: int = 900) -> np.ndarray:
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    cv2.putText(image, "Sample text line one", (20, 60), _FONT, 1.0, (0, 0, 0), 2)
    cv2.putText(image, "Sample text line two", (20, 140), _FONT, 1.0, (0, 0, 0), 2)
    cv2.putText(image, "Sample text line three", (20, 220), _FONT, 1.0, (0, 0, 0), 2)
    return image


def test_clean_page_gets_high_quality_score_and_no_recommendations() -> None:
    report = analyze_page_quality(_clean_text_page())
    assert report.quality_score >= 70.0
    assert report.quality_classification in ("EXCELLENT", "GOOD")
    assert report.exposure == "normal"


def test_blurry_page_is_flagged() -> None:
    sharp = _clean_text_page()
    blurry = cv2.GaussianBlur(sharp, (15, 15), 8)
    report = analyze_page_quality(blurry)
    assert report.blur_risk > 50.0


def test_skewed_page_recommends_deskew() -> None:
    image = _clean_text_page()
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width // 2, height // 2), 6.0, 1.0)
    skewed = cv2.warpAffine(image, matrix, (width, height), borderValue=(255, 255, 255))
    report = analyze_page_quality(skewed)
    assert abs(report.skew_angle) >= 1.0
    assert "deskew" in report.recommended_operations


def test_rotated_90_degrees_is_detected() -> None:
    image = _clean_text_page()
    rotated = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    report = analyze_page_quality(rotated)
    assert report.orientation == 90
    assert "orientation" in report.recommended_operations


def test_low_contrast_page_recommends_contrast_enhancement() -> None:
    image = _clean_text_page()
    low_contrast = (image.astype(np.float32) * 0.12 + 150 * 0.88).astype(np.uint8)
    report = analyze_page_quality(low_contrast)
    assert report.contrast_score < 60.0
    assert "contrast" in report.recommended_operations


def test_shadowed_page_recommends_background_clean() -> None:
    image = _clean_text_page()
    height, width = image.shape[:2]
    gradient = np.tile(np.linspace(0, 120, width), (height, 1)).astype(np.uint8)
    gradient_bgr = cv2.merge([gradient, gradient, gradient])
    shadowed = cv2.subtract(image, gradient_bgr)
    report = analyze_page_quality(shadowed)
    assert report.background_uniformity < 80.0
    assert "background_clean" in report.recommended_operations


def test_noisy_page_recommends_denoise() -> None:
    image = _clean_text_page()
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 25, image.shape).astype(np.int16)
    noisy = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    report = analyze_page_quality(noisy)
    assert report.noise_risk > 40.0
    assert "denoise" in report.recommended_operations


def test_sparse_text_page_is_not_falsely_flagged_overexposed() -> None:
    """Regression test for a real calibration bug found during development:
    a mostly-white document page (the normal case) was initially flagged
    as "overexposed" purely because raw mean luminance is naturally high
    when background dominates the page."""
    image = np.full((300, 900, 3), 255, dtype=np.uint8)
    cv2.putText(image, "Q1", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    report = analyze_page_quality(image)
    assert report.exposure == "normal"


def test_small_image_reports_small_text_risk() -> None:
    tiny = np.full((100, 150, 3), 255, dtype=np.uint8)
    report = analyze_page_quality(tiny)
    assert report.small_text_risk is True


def test_blank_page_does_not_raise() -> None:
    blank = np.full((300, 900, 3), 255, dtype=np.uint8)
    report = analyze_page_quality(blank)
    assert 0.0 <= report.quality_score <= 100.0


def test_to_metrics_dict_contains_all_fields() -> None:
    report = analyze_page_quality(_clean_text_page())
    metrics = report.to_metrics_dict()
    assert "blur_variance" in metrics
    assert "skew_angle" in metrics
    assert "document_type_hint" in metrics
    assert "recommended_operations" in metrics


@pytest.mark.parametrize(
    "score,expected",
    [(90.0, "EXCELLENT"), (75.0, "GOOD"), (55.0, "FAIR"), (35.0, "POOR"), (10.0, "CRITICAL")],
)
def test_classification_thresholds(score: float, expected: str) -> None:
    from app.services.document_intelligence.quality import _classify

    assert _classify(score) == expected
