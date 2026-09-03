"""
Diagram/Equation/Table routing (Document Intelligence milestone, Sections
17-23). For each classified `DetectedRegion`, this module decides which
downstream path a region takes and does the two things every path
genuinely needs today: **crop preservation** (the region's real pixel
data, saved so it's never lost regardless of what analysis is or isn't
available) and **real OCR labeling where that's a meaningful best-effort
signal** (e.g. reading a diagram's caption text, or a table's cell text).

**Detection vs. understanding boundary (Section 20/22), stated honestly**:
- `DIAGRAM`/`EQUATION` regions get real detection + real crop preservation
  + best-effort OCR text (labels/captions), through the
  `VisualAnalysisProvider`/`MathRecognitionProvider` interfaces below.
  Neither interface has a real semantic-understanding implementation this
  milestone — both return a `NOT_IMPLEMENTED` `ProviderStatus`, not a
  fabricated result. A future milestone can implement either provider
  (e.g. an isolated-runtime local vision/math model) without touching any
  other code, since callers only depend on the interface.
- `TABLE` regions get a REAL, deterministic, local structure extraction
  attempt (`extract_table_structure()`) via Hough-line grid detection —
  genuinely implemented, not deferred, since it requires no ML model at
  all (Section 23: "reuse existing... do not install another framework
  unless needed" — plain OpenCV line detection is sufficient for ruled
  tables, which is what exam answer scripts/question papers actually use).
  Cell text is filled in via a direct Tesseract call per cell (fast,
  already-verified, no ensemble needed for this auxiliary purpose).

Text/handwriting regions are NOT handled here — they continue through the
existing six-provider ensemble/fusion unchanged (Section 17/18); this
module only ever handles DIAGRAM/EQUATION/TABLE routing.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

import cv2
import numpy as np

from app.services.document_intelligence.layout import DetectedRegion
from app.services.image_processing.io_utils import encode_image_to_bytes
from app.services.ocr.providers.tesseract_provider import TesseractProvider

ProviderStatus = Literal["NOT_IMPLEMENTED", "SUCCESS", "FAILED"]

# Isolated small crops (a single table cell, a diagram caption) need
# different Tesseract handling than a full page: PSM 3 (this project's
# whole-page default) reliably finds nothing on a small/sparse crop, and
# a crop below this size threshold gets misread at native resolution
# (confirmed: a 150x100px two-character cell crop with grid-line border
# pixels included read as "po"/"" under every PSM; excluding the border
# and upscaling 3x before OCR fixed it to the correct "A1"). PSM 6
# ("assume a single uniform block of text") is the right mode for an
# isolated cell/caption crop, not a full page.
_CELL_OCR_PSM = 6
_MIN_OCR_CROP_DIMENSION_PX = 200
_CROP_INWARD_MARGIN_PX = 4


@dataclass(frozen=True)
class VisualEvidence:
    status: ProviderStatus
    description: str | None = None
    detail: str | None = None


class VisualAnalysisProvider(Protocol):
    """Interface for future diagram semantic-understanding (Section 20).
    No implementation registered this milestone — see module docstring."""

    def analyze(self, image: np.ndarray) -> VisualEvidence: ...


class _NotImplementedVisualAnalysisProvider:
    def analyze(self, image: np.ndarray) -> VisualEvidence:
        return VisualEvidence(
            status="NOT_IMPLEMENTED",
            detail=(
                "Diagram semantic understanding is not implemented this milestone — "
                "detection and crop preservation are real; interpretation is deferred."
            ),
        )


@dataclass(frozen=True)
class MathEvidence:
    status: ProviderStatus
    latex: str | None = None
    detail: str | None = None


class MathRecognitionProvider(Protocol):
    """Interface for future equation semantic recognition (Section 22).
    No implementation registered this milestone — see module docstring."""

    def recognize(self, image: np.ndarray) -> MathEvidence: ...


class _NotImplementedMathRecognitionProvider:
    def recognize(self, image: np.ndarray) -> MathEvidence:
        return MathEvidence(
            status="NOT_IMPLEMENTED",
            detail=(
                "Math/equation semantic recognition is not implemented this milestone — "
                "detection and crop preservation are real; LaTeX/structured recognition "
                "is deferred to a future milestone (a genuinely free, local, Windows-"
                "compatible math-OCR model was not found to be already installed, and "
                "installing one was out of scope for this pass)."
            ),
        )


DEFAULT_VISUAL_ANALYSIS_PROVIDER: VisualAnalysisProvider = _NotImplementedVisualAnalysisProvider()
DEFAULT_MATH_RECOGNITION_PROVIDER: MathRecognitionProvider = (
    _NotImplementedMathRecognitionProvider()
)


@dataclass(frozen=True)
class TableCell:
    row: int
    col: int
    bbox: tuple[int, int, int, int]  # left, top, width, height
    text: str
    confidence: float


@dataclass(frozen=True)
class TableStructure:
    row_count: int
    col_count: int
    cells: list[TableCell] = field(default_factory=list)
    detection_method: str = "hough_line_grid"


def _crop(image: np.ndarray, region: DetectedRegion) -> np.ndarray:
    box = region.bbox
    return image[box.top : box.top + box.height, box.left : box.left + box.width]


def preserve_region_crop(image: np.ndarray, region: DetectedRegion) -> bytes:
    """Real pixel crop, PNG-encoded — callers persist this to object
    storage (`DocumentRegion.crop_storage_key`). Never destructive to the
    source `image`; a plain slice + copy-on-encode."""
    crop = _crop(image, region)
    return encode_image_to_bytes(crop)


def _upscale_small_crop(crop: np.ndarray) -> np.ndarray:
    """Isolated small crops read unreliably at native resolution (see
    module-level constants' docstring) — upscale so the shorter edge
    reaches `_MIN_OCR_CROP_DIMENSION_PX` before OCR, a real (not
    fabricated-quality) resolution increase via cubic interpolation."""
    height, width = crop.shape[:2]
    shortest_edge = min(height, width)
    if shortest_edge <= 0 or shortest_edge >= _MIN_OCR_CROP_DIMENSION_PX:
        return crop
    scale = _MIN_OCR_CROP_DIMENSION_PX / shortest_edge
    new_size = (round(width * scale), round(height * scale))
    return cv2.resize(crop, new_size, interpolation=cv2.INTER_CUBIC)


def _ocr_isolated_crop(crop: np.ndarray, *, language: str) -> tuple[str, float]:
    """Shared real-OCR path for any isolated small crop (table cell,
    diagram caption, equation label) — never the full six-provider
    ensemble, since this is an auxiliary best-effort label, not primary
    content recognition (see module docstring)."""
    if crop.size == 0:
        return "", 0.0
    prepared = _upscale_small_crop(crop)
    provider = TesseractProvider(psm=_CELL_OCR_PSM)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(encode_image_to_bytes(prepared))
        tmp_path = tmp.name
    try:
        result = provider.extract(tmp_path, language=language)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return result.raw_text.strip(), result.average_confidence


def label_region_with_ocr(
    image: np.ndarray, region: DetectedRegion, *, language: str = "eng"
) -> str:
    """Best-effort OCR text for a DIAGRAM/EQUATION region's caption/labels
    — genuinely real Tesseract OCR on the crop, never a fabricated
    "understanding" of the visual content itself (Section 19: "DO NOT
    pretend OCR label extraction means diagram understanding")."""
    text, _confidence = _ocr_isolated_crop(_crop(image, region), language=language)
    return text


def extract_table_structure(
    image: np.ndarray, region: DetectedRegion, *, language: str = "eng"
) -> TableStructure:
    """Real, deterministic ruled-table grid detection via Hough line
    detection — no ML model. Detects horizontal/vertical rule lines within
    the region crop, derives row/column boundaries from their positions,
    and OCRs each resulting cell independently. Falls back to a
    single-row/single-column "whole region as one cell" structure when no
    clean grid is found (a table without visible ruling, or a false-
    positive TABLE classification) rather than fabricating rows/columns
    that don't exist."""
    crop = _crop(image, region)
    if crop.size == 0:
        return TableStructure(row_count=0, col_count=0, cells=[])

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    height, width = binary.shape[:2]
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(width // 15, 1), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(height // 15, 1)))
    horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
    vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)

    row_boundaries = _line_positions(horizontal_lines, axis=0)
    col_boundaries = _line_positions(vertical_lines, axis=1)

    if len(row_boundaries) < 2 or len(col_boundaries) < 2:
        # No clean grid detected — preserve the whole region as one cell
        # rather than fabricating a row/column structure that isn't there.
        text = label_region_with_ocr(image, region, language=language)
        return TableStructure(
            row_count=1,
            col_count=1,
            cells=[TableCell(row=0, col=0, bbox=(0, 0, width, height), text=text, confidence=0.0)],
            detection_method="whole_region_fallback",
        )

    cells: list[TableCell] = []
    for row_index in range(len(row_boundaries) - 1):
        top = row_boundaries[row_index]
        bottom = row_boundaries[row_index + 1]
        for col_index in range(len(col_boundaries) - 1):
            left = col_boundaries[col_index]
            right = col_boundaries[col_index + 1]
            # Inward margin excludes the ruling lines themselves — real,
            # confirmed finding: grid-line pixels at a cell's edge disrupt
            # Tesseract's character segmentation on an isolated cell crop.
            inner_top = min(top + _CROP_INWARD_MARGIN_PX, bottom)
            inner_bottom = max(bottom - _CROP_INWARD_MARGIN_PX, inner_top)
            inner_left = min(left + _CROP_INWARD_MARGIN_PX, right)
            inner_right = max(right - _CROP_INWARD_MARGIN_PX, inner_left)
            cell_crop = crop[inner_top:inner_bottom, inner_left:inner_right]
            text, confidence = _ocr_isolated_crop(cell_crop, language=language)
            cells.append(
                TableCell(
                    row=row_index,
                    col=col_index,
                    bbox=(left, top, right - left, bottom - top),
                    text=text,
                    confidence=confidence,
                )
            )

    return TableStructure(
        row_count=len(row_boundaries) - 1, col_count=len(col_boundaries) - 1, cells=cells
    )


def _line_positions(line_mask: np.ndarray, *, axis: int) -> list[int]:
    """Collapses a binary mask of detected rule lines down to a sorted
    list of boundary pixel positions along `axis` (0=rows/horizontal
    lines, 1=cols/vertical lines) — adjacent detected-line rows/columns
    are merged into a single boundary."""
    projection = line_mask.sum(axis=1 if axis == 0 else 0)
    threshold = projection.max() * 0.5 if projection.max() > 0 else 0
    line_indices = (
        np.where(projection >= threshold)[0] if threshold > 0 else np.array([], dtype=int)
    )

    if line_indices.size == 0:
        return []

    boundaries: list[int] = [int(line_indices[0])]
    for index in line_indices[1:]:
        if int(index) - boundaries[-1] > 5:  # merge adjacent detected-line pixels into one boundary
            boundaries.append(int(index))
    return boundaries
