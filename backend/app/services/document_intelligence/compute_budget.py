"""
Compute Budget Manager (Step 4 milestone, Sections 6-10).

This project's Celery worker processes one page at a time, one region at
a time — there is no existing worker pool that spawns multiple concurrent
model-inference processes per job (see `app.tasks.ocr_tasks`'s own
docstring: "one task instance blocks its worker slot for the whole
pipeline run"). This module does NOT invent a concurrency scheduler that
doesn't otherwise exist in this codebase; it makes the REAL bounds that
already apply — timeouts, routing that skips unnecessary work, and a
hard cap on how many visual/math analyses run per page — explicit,
centralized, and conservatively defaulted for a 6GB-VRAM laptop GPU,
rather than scattering magic numbers across `diagram_analysis.py`/
`math_recognition.py`/`ocr_tasks.py`.

Eco-efficiency routing (Section 6/54) is naturally free here: diagram
analysis and math recognition are only ever invoked for regions the
existing, already-verified layout/classification stage (Document
Intelligence milestone) has labeled `DIAGRAM`/`EQUATION` — a page with
zero such regions (pure text) triggers zero visual/math analysis calls,
with no extra flag or check required. `should_analyze_region()` below is
the single, auditable place that decision is made, so it's testable in
isolation rather than implied by scattered `if region.region_type ==
...` checks.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.document_intelligence.layout import DetectedRegion

# Conservative defaults for a 6GB-VRAM / 24GB-RAM laptop (Ryzen 7 /
# RTX 4050 class) — deliberately cautious, not tuned for throughput.
# Both pix2tex and the classical-vision diagram analyzer run CPU-only in
# this project (see this milestone's final report for measured resource
# usage), so GPU figures below are forward-looking bounds, not currently
# exercised numbers.
DEFAULT_MAX_VISUAL_REGIONS_PER_PAGE = 12
DEFAULT_MAX_MATH_REGIONS_PER_PAGE = 20
DEFAULT_DIAGRAM_ANALYSIS_TIMEOUT_SECONDS = 30.0
DEFAULT_MATH_RECOGNITION_TIMEOUT_SECONDS = 60.0
# downscale before analysis; never send an uncapped-resolution crop
DEFAULT_MAX_CROP_DIMENSION_PX = 2000


@dataclass(frozen=True)
class ComputeBudget:
    max_visual_regions_per_page: int = DEFAULT_MAX_VISUAL_REGIONS_PER_PAGE
    max_math_regions_per_page: int = DEFAULT_MAX_MATH_REGIONS_PER_PAGE
    diagram_analysis_timeout_seconds: float = DEFAULT_DIAGRAM_ANALYSIS_TIMEOUT_SECONDS
    math_recognition_timeout_seconds: float = DEFAULT_MATH_RECOGNITION_TIMEOUT_SECONDS
    max_crop_dimension_px: int = DEFAULT_MAX_CROP_DIMENSION_PX


DEFAULT_COMPUTE_BUDGET = ComputeBudget()


def should_analyze_region(
    region: DetectedRegion,
    *,
    analyzed_visual_count: int,
    analyzed_math_count: int,
    budget: ComputeBudget = DEFAULT_COMPUTE_BUDGET,
) -> bool:
    """The single, centralized eco-efficiency + resource-safety gate
    (Section 6/54): a TEXT/TABLE/other region never reaches diagram or
    math analysis at all (content-classification-driven routing, not a
    heavy model deciding it has nothing to do); a page with an unusually
    large number of detected diagram/equation regions is capped rather
    than analyzed unboundedly (Section 5's "no unbounded... inference
    workers")."""
    if region.region_type == "DIAGRAM":
        return analyzed_visual_count < budget.max_visual_regions_per_page
    if region.region_type == "EQUATION":
        return analyzed_math_count < budget.max_math_regions_per_page
    return False


def clamp_crop_dimensions(
    width: int, height: int, *, budget: ComputeBudget = DEFAULT_COMPUTE_BUDGET
) -> tuple[int, int]:
    """Returns a (possibly downscaled) target size preserving aspect
    ratio — never upscales, only bounds an oversized crop before it's
    handed to a model (Section 5/7's "max input resolution/crop size")."""
    longest_edge = max(width, height)
    if longest_edge <= budget.max_crop_dimension_px or longest_edge <= 0:
        return width, height
    scale = budget.max_crop_dimension_px / longest_edge
    return max(1, round(width * scale)), max(1, round(height * scale))
