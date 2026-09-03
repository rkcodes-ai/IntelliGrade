"""
PageQualityAnalyzer (Document Intelligence milestone) — deterministic,
explainable page-quality signals that drive `AdaptiveImageEnhancer`'s
per-page enhancement plan and the original-vs-enhanced selection
decision.

Every metric below is a real, reproducible measurement computed directly
from the pixel data — never a network call, never a trained/opaque
classifier, and every "risk"/"score" is documented with the formula that
produced it (Section 8's explicit "no mysterious arbitrary number" rule).
Wherever an equivalent measurement already exists in
`app.services.image_processing` (skew via `rotation.detect_rotation_angle`,
orientation via `orientation.detect_orientation`, perspective via
`perspective.estimate_perspective_risk`), this module reuses it directly
rather than re-deriving an equivalent metric a second way — Section 13's
"reuse before adding" doctrine applies just as much to metrics as it does
to whole libraries. Background/contrast/brightness/document-type all share
one Otsu ink/background mask (the same threshold call
`rotation.py`/`trim_margins.py`/`blank_detection.py` already use
elsewhere), computed once per page rather than four times.

No new third-party dependency was introduced for this module — every
computation uses `opencv-python-headless`/`numpy`, both already
installed and already relied on throughout `image_processing`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import cv2
import numpy as np

from app.services.image_processing.io_utils import to_grayscale
from app.services.image_processing.orientation import detect_orientation
from app.services.image_processing.perspective import estimate_perspective_risk
from app.services.image_processing.rotation import detect_rotation_angle

QualityClassification = Literal["EXCELLENT", "GOOD", "FAIR", "POOR", "CRITICAL"]
DocumentTypeHint = Literal["PRINTED_DOCUMENT", "HANDWRITTEN_DOCUMENT", "MIXED_DOCUMENT", "UNKNOWN"]
Exposure = Literal["underexposed", "normal", "overexposed"]

# Documented, configurable thresholds — reasonable starting defaults (same
# "documented default, not a measured constant" framing as
# `app.services.ocr.fusion.DEFAULT_PROVIDER_WEIGHTS`), tunable once real
# benchmark evidence from `tests/test_document_intelligence_quality.py`
# and production data exists.
_BLUR_SHARP_VARIANCE = 350.0  # Laplacian variance at/above this = "sharp"
_BLUR_BLURRY_VARIANCE = 60.0  # at/below this = "blurry"
_SKEW_DESKEW_THRESHOLD_DEGREES = 0.75
_CONTRAST_GOOD_STD = 55.0
# Document images are mostly white/light background with a small dark-ink
# fraction, so raw mean luminance runs high for *any* well-exposed page —
# unlike `brightness.py`'s `_TARGET_MEAN_LUMINANCE=150` (tuned for that
# module's auto-correction gain math, not for "is this page well-exposed").
# Exposure here is judged from the 95th/5th percentiles instead — a proxy
# for "how bright is the background" / "how dark is the darkest ink" —
# so a normal white-page-with-black-text scan is correctly "normal", not
# flagged as overexposed just for having a mostly-white background.
_BRIGHTNESS_IDEAL_BACKGROUND_P95 = 245.0
_BRIGHTNESS_UNDEREXPOSED_P95 = 150.0  # background itself isn't bright -> whole page dim
_BRIGHTNESS_OVEREXPOSED_P5 = 180.0  # even the darkest ink is washed out -> blown highlights
_NOISE_SIGNIFICANT_SIGMA = 6.0
_BACKGROUND_UNEVEN_STD = 18.0
_PERSPECTIVE_SIGNIFICANT_RISK = 25.0
_COMPRESSION_SIGNIFICANT_RISK = 35.0
_SMALL_TEXT_RISK_LONG_EDGE_PX = 1200
_A4_ASPECT_RATIO = 11.69 / 8.27  # height / width, portrait

_SCORE_WEIGHTS: dict[str, float] = {
    "sharpness": 0.25,
    "contrast": 0.15,
    "brightness": 0.10,
    "noise": 0.15,
    "resolution": 0.10,
    "background": 0.10,
    "perspective": 0.10,
    "compression": 0.05,
}

_CLASSIFICATION_THRESHOLDS: tuple[tuple[float, QualityClassification], ...] = (
    (85.0, "EXCELLENT"),
    (70.0, "GOOD"),
    (50.0, "FAIR"),
    (30.0, "POOR"),
)


@dataclass(frozen=True)
class PageQualityReport:
    quality_score: float
    quality_classification: QualityClassification
    blur_variance: float
    blur_risk: float  # 0-100, higher = blurrier
    skew_angle: float
    orientation: int
    contrast_score: float  # 0-100, higher = better separation
    brightness_mean: float
    brightness_score: float  # 0-100, higher = closer to target
    exposure: Exposure
    noise_sigma: float
    noise_risk: float  # 0-100, higher = noisier
    width_px: int
    height_px: int
    effective_dpi_estimate: float | None
    small_text_risk: bool
    background_uniformity: float  # 0-100, higher = more uniform (better)
    perspective_risk: float  # 0-100, higher = more distorted
    compression_artifact_risk: float  # 0-100, higher = more blocky
    document_type_hint: DocumentTypeHint
    document_type_confidence: float
    recommended_operations: list[str] = field(default_factory=list)

    def to_metrics_dict(self) -> dict[str, Any]:
        """Full structured dump for persistence (`AnswerScriptPage.quality_metrics`)."""
        return {
            "blur_variance": self.blur_variance,
            "blur_risk": self.blur_risk,
            "skew_angle": self.skew_angle,
            "orientation": self.orientation,
            "contrast_score": self.contrast_score,
            "brightness_mean": self.brightness_mean,
            "brightness_score": self.brightness_score,
            "exposure": self.exposure,
            "noise_sigma": self.noise_sigma,
            "noise_risk": self.noise_risk,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "effective_dpi_estimate": self.effective_dpi_estimate,
            "small_text_risk": self.small_text_risk,
            "background_uniformity": self.background_uniformity,
            "perspective_risk": self.perspective_risk,
            "compression_artifact_risk": self.compression_artifact_risk,
            "document_type_hint": self.document_type_hint,
            "document_type_confidence": self.document_type_confidence,
            "recommended_operations": self.recommended_operations,
        }


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return float(max(low, min(high, value)))


def _blur_metrics(gray: np.ndarray) -> tuple[float, float]:
    variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if variance >= _BLUR_SHARP_VARIANCE:
        risk = 0.0
    elif variance <= _BLUR_BLURRY_VARIANCE:
        risk = 100.0
    else:
        span = _BLUR_SHARP_VARIANCE - _BLUR_BLURRY_VARIANCE
        risk = 100.0 * (1.0 - (variance - _BLUR_BLURRY_VARIANCE) / span)
    return variance, _clamp(risk)


def _contrast_score(gray: np.ndarray, *, ink_mask: np.ndarray) -> float:
    """Foreground/background mean separation, not raw whole-image pixel
    std — global std is misleadingly low on a page with sparse text (most
    pixels are uniform background regardless of how well the actual ink
    stands out), which would otherwise recommend contrast enhancement on
    perfectly good pages purely for having little text on them."""
    ink_pixels = gray[ink_mask > 0]
    background_pixels = gray[ink_mask == 0]
    if ink_pixels.size < 20 or background_pixels.size < 20:
        # Not enough of one class to judge separation (e.g. a near-blank
        # page) — fall back to whole-image std as the only signal available.
        return _clamp(100.0 * (float(gray.std()) / _CONTRAST_GOOD_STD))

    separation = float(background_pixels.mean() - ink_pixels.mean())
    return _clamp(100.0 * (separation / _CONTRAST_GOOD_STD))


def _brightness_metrics(gray: np.ndarray, *, ink_mask: np.ndarray) -> tuple[float, float, Exposure]:
    """`p95` estimates background brightness directly (background is
    always the large majority of a document page, so the 95th percentile
    is a robust background sample regardless of how much ink is on the
    page). The darkest-ink estimate, by contrast, uses the shared
    Otsu-threshold ink mask — a blind whole-image low percentile is
    unreliable when ink coverage is small (e.g. a single header line on an
    otherwise-blank page), since the 5th percentile would then land on
    background, not ink, and wrongly read as "overexposed" (no dark
    pixels found) even though the actual ink present is perfectly dark."""
    mean = float(gray.mean())
    p95 = float(np.percentile(gray, 95))

    ink_pixels = gray[ink_mask > 0]
    darkest_ink_estimate = float(np.percentile(ink_pixels, 10)) if ink_pixels.size >= 20 else p95

    if p95 <= _BRIGHTNESS_UNDEREXPOSED_P95:
        exposure: Exposure = "underexposed"
    elif darkest_ink_estimate >= _BRIGHTNESS_OVEREXPOSED_P5:
        exposure = "overexposed"
    else:
        exposure = "normal"

    distance = abs(p95 - _BRIGHTNESS_IDEAL_BACKGROUND_P95)
    score = _clamp(100.0 - (distance / _BRIGHTNESS_IDEAL_BACKGROUND_P95) * 100.0)
    return mean, score, exposure


def _noise_metrics(gray: np.ndarray) -> tuple[float, float]:
    """Immerkaer's fast noise-variance estimator: convolve with a Laplacian
    mask discretized to be robust to actual image edges, then rescale by
    the mask's own normalization constant. A real, well-known, closed-form
    estimator (not a fabricated heuristic) — see J. Immerkaer, "Fast Noise
    Variance Estimation", Computer Vision and Image Understanding, 1996."""
    height, width = gray.shape[:2]
    if height < 3 or width < 3:
        return 0.0, 0.0
    laplacian_mask = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float64)
    convolved = cv2.filter2D(gray.astype(np.float64), -1, laplacian_mask)
    denominator = 6 * (width - 2) * (height - 2)
    sigma = float(np.sqrt(np.pi / 2) * np.sum(np.abs(convolved)) / (denominator + 1e-9))
    risk = _clamp(100.0 * (sigma / _NOISE_SIGNIFICANT_SIGMA))
    return sigma, risk


def _background_uniformity(gray: np.ndarray, *, ink_mask: np.ndarray) -> float:
    """Measures illumination evenness using only pixels the page's own
    Otsu threshold (the same threshold `rotation.py`/`trim_margins.py`/
    `blank_detection.py` already use elsewhere in this pipeline) classifies
    as *background*, not ink — sampling the raw grayscale value at those
    locations directly. A shadow/gradient across the page shows up as high
    variance among background-only pixels; even lighting shows up as low
    variance. (An earlier version of this function measured variance of
    `background_clean.clean_background`'s morphological-open estimate
    instead — but that estimate is measurably distorted by nearby text
    density, not just by real illumination unevenness, which produced
    false "uneven background" readings on a perfectly evenly-lit page with
    a lot of text on it. Sampling confirmed background-only pixels avoids
    that failure mode.)"""
    dilated_ink_mask = cv2.dilate(ink_mask, np.ones((15, 15), np.uint8))
    background_pixels = gray[dilated_ink_mask == 0]

    if background_pixels.size < 100:  # not enough confirmed background to judge
        return 100.0

    std = float(background_pixels.std())
    return _clamp(100.0 - (std / _BACKGROUND_UNEVEN_STD) * 100.0)


def _compression_artifact_risk(gray: np.ndarray) -> float:
    """Classic JPEG-blockiness estimate: JPEG's 8x8 DCT blocks introduce a
    real, measurable discontinuity at block boundaries that isn't present
    within a block — the ratio of mean gradient magnitude *at* multiples
    of 8 pixels vs *away* from them is a genuine, well-known blockiness
    signal, not a fabricated number."""
    height, width = gray.shape[:2]
    if height < 16 or width < 16:
        return 0.0

    horizontal_diff = np.abs(np.diff(gray.astype(np.int16), axis=1))
    boundary_columns = np.arange(7, width - 1, 8)
    if boundary_columns.size == 0:
        return 0.0
    all_columns = np.arange(horizontal_diff.shape[1])
    non_boundary_columns = np.setdiff1d(all_columns, boundary_columns)
    if non_boundary_columns.size == 0:
        return 0.0

    boundary_energy = float(horizontal_diff[:, boundary_columns].mean())
    non_boundary_energy = float(horizontal_diff[:, non_boundary_columns].mean()) + 1e-6
    ratio = boundary_energy / non_boundary_energy
    # ratio ~1.0 -> no detectable blocking; higher ratio -> more blocking.
    risk = _clamp((ratio - 1.0) * 100.0)
    return risk


def _resolution_metrics(image: np.ndarray) -> tuple[int, int, float | None, bool, float]:
    height, width = image.shape[:2]
    long_edge = max(height, width)
    short_edge = min(height, width)
    small_text_risk = long_edge < _SMALL_TEXT_RISK_LONG_EDGE_PX

    effective_dpi: float | None = None
    if short_edge > 0:
        aspect_ratio = long_edge / short_edge
        # Only estimate DPI when the page's proportions plausibly resemble
        # A4 — otherwise we'd be fabricating a physical-size assumption
        # for a document we have no evidence is that shape.
        if abs(aspect_ratio - _A4_ASPECT_RATIO) < 0.15:
            effective_dpi = round(short_edge / 8.27, 1)

    resolution_score = _clamp(100.0 * min(1.0, long_edge / _SMALL_TEXT_RISK_LONG_EDGE_PX))
    return width, height, effective_dpi, small_text_risk, resolution_score


def _document_type_hint(*, ink_mask: np.ndarray) -> tuple[DocumentTypeHint, float]:
    """Heuristic, not a trained classifier: printed text is composed of a
    small number of near-identical glyph strokes with fairly uniform
    stroke width; handwriting's stroke width varies far more from
    character to character. Estimated via a distance-transform-based
    per-component stroke-width proxy and its coefficient of variation
    (std/mean) across connected ink components — high CoV suggests
    handwriting, low CoV suggests print. Confidence reflects how many
    components were available to measure, not a calibrated probability."""
    binary = ink_mask
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

    if num_labels <= 1:
        return "UNKNOWN", 0.0

    distance = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    stroke_widths: list[float] = []
    for label_index in range(1, num_labels):
        area = stats[label_index, cv2.CC_STAT_AREA]
        if area < 4:  # ignore speckle noise
            continue
        component_mask = labels == label_index
        component_distances = distance[component_mask]
        if component_distances.size == 0:
            continue
        stroke_widths.append(float(component_distances.max()) * 2.0)

    if len(stroke_widths) < 5:
        return "UNKNOWN", 0.0

    widths = np.array(stroke_widths)
    mean_width = float(widths.mean())
    if mean_width <= 0:
        return "UNKNOWN", 0.0
    coefficient_of_variation = float(widths.std() / mean_width)

    confidence = _clamp(min(100.0, len(stroke_widths) * 2.0)) / 100.0
    if coefficient_of_variation < 0.35:
        return "PRINTED_DOCUMENT", confidence
    if coefficient_of_variation > 0.6:
        return "HANDWRITTEN_DOCUMENT", confidence
    return "MIXED_DOCUMENT", confidence


def _classify(score: float) -> QualityClassification:
    for threshold, label in _CLASSIFICATION_THRESHOLDS:
        if score >= threshold:
            return label
    return "CRITICAL"


def _recommended_operations(
    *,
    skew_angle: float,
    contrast_score: float,
    brightness_score: float,
    exposure: Exposure,
    noise_risk: float,
    background_uniformity: float,
    perspective_risk: float,
    orientation: int,
) -> list[str]:
    operations: list[str] = []
    if orientation != 0:
        operations.append("orientation")
    if abs(skew_angle) >= _SKEW_DESKEW_THRESHOLD_DEGREES:
        operations.append("deskew")
    if perspective_risk >= _PERSPECTIVE_SIGNIFICANT_RISK:
        operations.append("perspective")
    if background_uniformity < (100.0 - _BACKGROUND_UNEVEN_STD):
        operations.append("background_clean")
    if contrast_score < 60.0:
        operations.append("contrast")
    if exposure != "normal":
        operations.append("brightness")
    if noise_risk > 40.0:
        operations.append("denoise")
    return operations


def analyze_page_quality(image: np.ndarray) -> PageQualityReport:
    """Compute a full `PageQualityReport` for one already-loaded page
    image (BGR `np.ndarray`, same convention as every `image_processing`
    step). Never raises for a structurally valid image — callers wrap
    this in a try/except only to guard against a genuinely corrupt/
    zero-size image (Section 28: quality-analysis failure -> use original)."""
    gray = to_grayscale(image)
    # One shared Otsu ink/background mask reused by every metric below
    # that needs to distinguish ink from background — computed once,
    # consistent with `rotation.py`/`trim_margins.py`/`blank_detection.py`'s
    # existing convention of the same Otsu call, and avoids 4 independent
    # (and potentially inconsistent) threshold computations per page.
    _, ink_mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    blur_variance, blur_risk = _blur_metrics(gray)
    skew_angle = detect_rotation_angle(image)
    orientation = detect_orientation(image)
    contrast_score = _contrast_score(gray, ink_mask=ink_mask)
    brightness_mean, brightness_score, exposure = _brightness_metrics(gray, ink_mask=ink_mask)
    noise_sigma, noise_risk = _noise_metrics(gray)
    width, height, effective_dpi, small_text_risk, resolution_score = _resolution_metrics(image)
    background_uniformity = _background_uniformity(gray, ink_mask=ink_mask)
    perspective_risk = estimate_perspective_risk(image)
    compression_risk = _compression_artifact_risk(gray)
    document_type_hint, document_type_confidence = _document_type_hint(ink_mask=ink_mask)

    sharpness_score = 100.0 - blur_risk
    noise_ok_score = 100.0 - noise_risk
    perspective_ok_score = 100.0 - perspective_risk
    compression_ok_score = 100.0 - compression_risk

    quality_score = _clamp(
        _SCORE_WEIGHTS["sharpness"] * sharpness_score
        + _SCORE_WEIGHTS["contrast"] * contrast_score
        + _SCORE_WEIGHTS["brightness"] * brightness_score
        + _SCORE_WEIGHTS["noise"] * noise_ok_score
        + _SCORE_WEIGHTS["resolution"] * resolution_score
        + _SCORE_WEIGHTS["background"] * background_uniformity
        + _SCORE_WEIGHTS["perspective"] * perspective_ok_score
        + _SCORE_WEIGHTS["compression"] * compression_ok_score
    )

    recommended_operations = _recommended_operations(
        skew_angle=skew_angle,
        contrast_score=contrast_score,
        brightness_score=brightness_score,
        exposure=exposure,
        noise_risk=noise_risk,
        background_uniformity=background_uniformity,
        perspective_risk=perspective_risk,
        orientation=orientation,
    )

    return PageQualityReport(
        quality_score=quality_score,
        quality_classification=_classify(quality_score),
        blur_variance=blur_variance,
        blur_risk=blur_risk,
        skew_angle=skew_angle,
        orientation=orientation,
        contrast_score=contrast_score,
        brightness_mean=brightness_mean,
        brightness_score=brightness_score,
        exposure=exposure,
        noise_sigma=noise_sigma,
        noise_risk=noise_risk,
        width_px=width,
        height_px=height,
        effective_dpi_estimate=effective_dpi,
        small_text_risk=small_text_risk,
        background_uniformity=background_uniformity,
        perspective_risk=perspective_risk,
        compression_artifact_risk=compression_risk,
        document_type_hint=document_type_hint,
        document_type_confidence=document_type_confidence,
        recommended_operations=recommended_operations,
    )
