"""
AdaptiveImageEnhancer (Document Intelligence milestone) — turns a
`PageQualityReport` into a concrete, minimal enhancement plan and applies
it, reusing the EXISTING `app.services.image_processing` step functions
(never re-implementing denoise/contrast/deskew/etc. a second time).

The key behavioral difference from the pre-existing `PreprocessingPipeline`
(which always runs its configured step list unconditionally on every
page) is that this module only ever includes a step in the plan when
`PageQualityReport.recommended_operations` actually flagged it — a clean
page's plan is empty, and `enhance_page()` returns the original image
unchanged (Section 5/41's "no unnecessary computation" / "fast path for
clean pages" requirement).

Handwriting/diagram-safe profiles (Sections 10/11): destructive,
detail-erasing steps (`adaptive_threshold`, aggressive `denoise`,
morphological `background_clean`) are downgraded or skipped outright when
the page is likely handwritten or likely contains significant non-text
visual content, since those operations can erase thin strokes, dots,
decimal points, and diagram lines. This is a conservative *profile*
decision layered on top of the quality-driven plan, not a separate
pipeline.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from app.services.document_intelligence.quality import PageQualityReport
from app.services.image_processing.background_clean import clean_background
from app.services.image_processing.brightness import correct_brightness
from app.services.image_processing.contrast import enhance_contrast
from app.services.image_processing.denoise import denoise
from app.services.image_processing.deskew import deskew
from app.services.image_processing.orientation import correct_orientation
from app.services.image_processing.perspective import correct_perspective

EnhancementProfile = Literal["printed", "handwritten", "diagram_safe", "mixed"]

# Steps that are safe to run on any content, including handwriting/diagrams
# — geometric corrections and mild brightness/contrast adjustments don't
# threaten thin strokes the way binarization/aggressive-denoise/morphology do.
_ALWAYS_SAFE_STEPS = frozenset({"orientation", "deskew", "perspective", "brightness", "contrast"})
# Steps downgraded (denoise -> a much gentler strength) or skipped entirely
# for handwriting/diagram-risk pages — see module docstring.
_DESTRUCTIVE_STEPS = frozenset({"denoise", "background_clean"})

_CONSERVATIVE_DENOISE_STRENGTH = 4  # vs. `denoise()`'s own default of 10


@dataclass(frozen=True)
class EnhancementResult:
    image: np.ndarray
    operations_applied: list[str]
    profile: EnhancementProfile
    processing_time_ms: int
    skipped_operations: list[dict[str, str]] = field(default_factory=list)


def _resolve_profile(quality: PageQualityReport, *, has_diagram_risk: bool) -> EnhancementProfile:
    if has_diagram_risk:
        return "diagram_safe"
    if quality.document_type_hint == "HANDWRITTEN_DOCUMENT":
        return "handwritten"
    if quality.document_type_hint == "MIXED_DOCUMENT":
        return "mixed"
    return "printed"


def build_enhancement_plan(
    quality: PageQualityReport, *, has_diagram_risk: bool = False
) -> tuple[list[str], EnhancementProfile]:
    """Pure planning function (no image I/O) — returns the ordered step
    list `enhance_page()` will run, plus the resolved safety profile.
    Exposed separately from `enhance_page()` so tests can assert on the
    *plan* without needing a real image, and so the plan can be recorded
    in `enhancement_metadata` even when the page turns out not to need it."""
    profile = _resolve_profile(quality, has_diagram_risk=has_diagram_risk)
    plan: list[str] = []

    for operation in quality.recommended_operations:
        if profile in ("handwritten", "diagram_safe") and operation in _DESTRUCTIVE_STEPS:
            # Downgrade denoise to a conservative strength rather than
            # dropping it outright — real, significant noise still
            # impairs OCR on a handwritten page; skip `background_clean`
            # instead, since its morphological approach is the step most
            # likely to visibly erase thin strokes.
            if operation == "denoise":
                plan.append(operation)
            continue
        plan.append(operation)

    # Keep the pipeline's own sensible ordering (geometry before
    # tone/denoise) regardless of the order quality signals happened to
    # be flagged in.
    ordering = [
        "orientation",
        "deskew",
        "perspective",
        "background_clean",
        "contrast",
        "brightness",
        "denoise",
    ]
    plan.sort(key=lambda step: ordering.index(step) if step in ordering else len(ordering))
    return plan, profile


def enhance_page(
    image: np.ndarray, quality: PageQualityReport, *, has_diagram_risk: bool = False
) -> EnhancementResult:
    """Applies `build_enhancement_plan()`'s plan to `image`. An empty plan
    (clean page) returns the original image completely untouched — no
    copy, no no-op transform — which is the actual fast path this
    function exists to provide."""
    started = time.perf_counter()
    plan, profile = build_enhancement_plan(quality, has_diagram_risk=has_diagram_risk)

    if not plan:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return EnhancementResult(
            image=image, operations_applied=[], profile=profile, processing_time_ms=elapsed_ms
        )

    result = image
    applied: list[str] = []
    for step in plan:
        if step == "orientation":
            result = correct_orientation(result, rotation=quality.orientation)
        elif step == "deskew":
            result = deskew(result, angle=quality.skew_angle)
        elif step == "perspective":
            result = correct_perspective(result)
        elif step == "background_clean":
            result = clean_background(result)
        elif step == "contrast":
            result = enhance_contrast(result)
        elif step == "brightness":
            result = correct_brightness(result)
        elif step == "denoise":
            strength = (
                _CONSERVATIVE_DENOISE_STRENGTH if profile in ("handwritten", "diagram_safe") else 10
            )
            result = denoise(result, strength=strength)
        applied.append(step)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return EnhancementResult(
        image=result, operations_applied=applied, profile=profile, processing_time_ms=elapsed_ms
    )
