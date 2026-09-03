"""
Unified layout/region detection (Document Intelligence milestone, Section
13/14). Reuses Surya's real, already-installed `LayoutPredictor` (see
`app.services.ocr.isolated_runners.surya_runner`'s `layout()` mode) via
the EXISTING isolated-runtime bridge built for the OCR ensemble milestone
— no new venv, no new model, no new third-party dependency.

**Why Surya alone, not a multi-detector ensemble**: audited docTR and
PaddleOCR before writing this module (Section 13's explicit requirement).
docTR's `ocr_predictor` (already verified working) only detects/recognizes
text lines — it has no region-*type* classification (no notion of
"this box is a table vs a diagram"). PaddleOCR's `PPStructure` does have
real table/layout detection, but — as `providers/paddleocr_provider.py`'s
own docstring already documents — it was never ported to paddleocr 3.x's
`PPStructureV3` API and is not runtime-verified; fixing that was out of
scope for the OCR milestone and remains out of scope here, since Surya's
`LayoutPredictor` already provides a complete, real, verified region-type
vocabulary (`Text`/`TextInlineMath`/`Equation`/`Table`/`Picture`/`Figure`/
`Handwriting`/`PageHeader`/`PageFooter`/`SectionHeader`/`Caption`/
`Footnote`/`ListItem`/`Form`/`TableOfContents`/`Code`/`Blank` — see
`surya.layout.model.config.ID_TO_LABEL`) that alone covers nearly every
region type this milestone's `REGION_TYPES` vocabulary needs. Installing
a second or third real layout model on top of that would be exactly the
"install a fourth layout framework merely because one exists" outcome
Section 13 explicitly forbids.

`reconcile_regions()` below is still written to accept multiple detector
outputs generically (list of `(source_name, list[DetectedRegion])`) so a
second real detector can be added later without changing its signature —
this milestone only ever feeds it Surya's output, honestly reflected in
`DetectedRegion.source_detector`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.services.ocr.base import BoundingBox
from app.services.ocr.exceptions import OCRIsolatedRuntimeInferenceError
from app.services.ocr.isolated_runtime import (
    RUNNERS_DIR,
    default_isolated_python,
    invoke_isolated_runtime,
)

settings = get_settings()
_RUNNER_SCRIPT = RUNNERS_DIR / "surya_runner.py"

# Unified region-type vocabulary (Section 14's `PageRegion.region_type`).
REGION_TYPES = (
    "PRINTED_TEXT",
    "HANDWRITTEN_TEXT",
    "QUESTION_NUMBER",
    "MARKS",
    "DIAGRAM",
    "TABLE",
    "EQUATION",
    "HEADER",
    "FOOTER",
    "PAGE_NUMBER",
    "IMAGE",
    "OTHER",
)

# Surya's real label vocabulary -> this project's unified region types.
# Never invented — every key below is a genuine `ID_TO_LABEL` value.
_SURYA_LABEL_TO_REGION_TYPE: dict[str, str] = {
    "Text": "PRINTED_TEXT",
    "ListItem": "PRINTED_TEXT",
    "TextInlineMath": "EQUATION",
    "Equation": "EQUATION",
    "Table": "TABLE",
    "Form": "TABLE",
    "Picture": "DIAGRAM",
    "Figure": "DIAGRAM",
    "Handwriting": "HANDWRITTEN_TEXT",
    "PageHeader": "HEADER",
    "SectionHeader": "HEADER",
    "PageFooter": "FOOTER",
    "Footnote": "FOOTER",
    "Caption": "OTHER",
    "Code": "OTHER",
    "TableOfContents": "OTHER",
    "Blank": "OTHER",
}


@dataclass(frozen=True)
class DetectedRegion:
    region_type: str
    bbox: BoundingBox
    confidence: float
    source_detector: str
    reading_order: int
    source_label: str  # the detector's own native label, preserved for audit


def _python_exe() -> Path:
    configured = settings.OCR_SURYA_PYTHON
    return Path(configured) if configured else default_isolated_python(".venv-surya")


def detect_regions_surya(image_path: str) -> list[DetectedRegion]:
    """Real region detection via Surya's `LayoutPredictor`. Raises the
    same `OCRIsolatedRuntime*` exceptions any other bridged provider does
    on failure — callers (the Celery pipeline) must catch and fall back
    to full-page OCR per Section 28, exactly like every other optional
    Document Intelligence stage."""
    python_exe = _python_exe()
    result = invoke_isolated_runtime(
        python_exe=python_exe,
        runner_script=_RUNNER_SCRIPT,
        request={"image_path": image_path, "mode": "layout"},
        startup_timeout=settings.OCR_ISOLATED_RUNTIME_STARTUP_TIMEOUT_SECONDS,
        inference_timeout=settings.OCR_ISOLATED_RUNTIME_INFERENCE_TIMEOUT_SECONDS,
    )
    payload = result.payload
    if not payload.get("success", True):
        raise OCRIsolatedRuntimeInferenceError(payload.get("error", "unknown Surya layout error"))

    regions: list[DetectedRegion] = []
    for index, raw_region in enumerate(payload.get("regions", [])):
        label = raw_region["label"]
        region_type = _SURYA_LABEL_TO_REGION_TYPE.get(label, "OTHER")
        bbox_data = raw_region["bbox"]
        regions.append(
            DetectedRegion(
                region_type=region_type,
                bbox=BoundingBox(
                    left=int(bbox_data["left"]),
                    top=int(bbox_data["top"]),
                    width=int(bbox_data["width"]),
                    height=int(bbox_data["height"]),
                ),
                confidence=float(raw_region["confidence"]),
                source_detector="surya_layout",
                reading_order=index,
                source_label=label,
            )
        )
    return regions


def _iou(a: BoundingBox, b: BoundingBox) -> float:
    a_left, a_top, a_right, a_bottom = a.left, a.top, a.left + a.width, a.top + a.height
    b_left, b_top, b_right, b_bottom = b.left, b.top, b.left + b.width, b.top + b.height

    inter_left = max(a_left, b_left)
    inter_top = max(a_top, b_top)
    inter_right = min(a_right, b_right)
    inter_bottom = min(a_bottom, b_bottom)
    if inter_right <= inter_left or inter_bottom <= inter_top:
        return 0.0

    intersection = (inter_right - inter_left) * (inter_bottom - inter_top)
    union = a.width * a.height + b.width * b.height - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def reconcile_regions(
    detector_outputs: list[tuple[str, list[DetectedRegion]]], *, iou_threshold: float = 0.5
) -> list[DetectedRegion]:
    """Merges regions from one or more detectors into one unified,
    non-duplicated region list (Section 15) using geometric IoU — deliberately
    deterministic geometry, not a second ML model, per Section 15's own
    "do not build an unnecessarily huge ML ensemble if deterministic
    geometry solves the problem" guidance. When two regions from
    different detectors overlap above `iou_threshold`, the higher-
    confidence one wins and the other is dropped as a duplicate; when only
    one detector contributed (this milestone's actual situation — see
    module docstring), this is a no-op pass-through in detector-confidence
    order."""
    all_regions: list[DetectedRegion] = []
    for _source_name, regions in detector_outputs:
        all_regions.extend(regions)

    if len(detector_outputs) <= 1:
        return sorted(all_regions, key=lambda r: r.reading_order)

    all_regions.sort(key=lambda r: r.confidence, reverse=True)
    kept: list[DetectedRegion] = []
    for region in all_regions:
        if any(_iou(region.bbox, kept_region.bbox) >= iou_threshold for kept_region in kept):
            continue
        kept.append(region)

    kept.sort(key=lambda r: (r.bbox.top, r.bbox.left))
    return [
        DetectedRegion(
            region_type=region.region_type,
            bbox=region.bbox,
            confidence=region.confidence,
            source_detector=region.source_detector,
            reading_order=index,
            source_label=region.source_label,
        )
        for index, region in enumerate(kept)
    ]
