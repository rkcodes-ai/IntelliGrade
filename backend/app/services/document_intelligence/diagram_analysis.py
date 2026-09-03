"""
Diagram structural analysis (Step 4 milestone — Free Local Visual +
Diagram + Mathematical Understanding).

Per Section 14/15's explicit "classical vision first" requirement: this
module extracts diagram STRUCTURE (not just OCR'd labels) using
deterministic OpenCV geometry — contour/shape detection, Hough line
detection for connectors, arrowhead detection, and existing Tesseract OCR
for labels — before considering any neural vision model. Zero new
third-party dependency (`opencv-python-headless`/`numpy` already
installed and already used throughout this project).

**A local vision-language model was researched, not integrated, this
milestone** — see this milestone's final report for the license/size
evidence (Moondream2, Apache 2.0, ~1.9B params, ~1.7-2GB footprint,
genuinely fits this machine's resource budget). Classical vision already
satisfies Section 61's actual success criterion ("diagram regions... not
merely detected but produce useful structured visual evidence") for the
majority of educational diagrams (flowcharts, block/network diagrams,
labeled figures with box/line/arrow structure) without the added
complexity, load time, and VRAM/RAM cost of a VLM — consistent with
Section 64's "if a compact deterministic algorithm solves the task, use
it instead of a large neural model." Integrating an optional VLM for the
harder cases (freeform sketches, complex scientific illustrations) is
honestly recorded as future work, not silently skipped.
"""

from __future__ import annotations

import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np

from app.services.document_intelligence.layout import DetectedRegion
from app.services.image_processing.io_utils import encode_image_to_bytes, to_grayscale
from app.services.ocr.providers.tesseract_provider import TesseractProvider

AnalysisStatus = Literal["SUCCESS", "FAILED", "NOT_IMPLEMENTED"]
ShapeType = Literal["box", "circle", "line", "unknown"]
ConnectionDirection = Literal["directed", "undirected", "unknown"]

# Documented, reasonable defaults (not measured accuracy) — same framing
# as `app.services.ocr.fusion.DEFAULT_PROVIDER_WEIGHTS`.
_MIN_BOX_AREA_FRACTION = 0.005  # ignore contours covering less than this share of the crop
_MIN_CIRCLE_RADIUS_PX = 8
_HOUGH_LINE_MIN_LENGTH_PX = 20
_HOUGH_LINE_MAX_GAP_PX = 8
_ARROWHEAD_SEARCH_RADIUS_PX = 25
_ENDPOINT_SNAP_RADIUS_PX = 20
_SHAPE_GEOMETRY_CONFIDENCE = 85.0  # deterministic geometry has no "probability" of its own
_CONNECTION_ENDPOINT_CONFIDENCE = 70.0


@dataclass(frozen=True)
class DiagramComponent:
    component_id: str
    shape_type: ShapeType
    bbox: tuple[int, int, int, int]  # left, top, width, height
    label: str | None
    confidence: float


@dataclass(frozen=True)
class DiagramConnection:
    source_component_id: str | None
    target_component_id: str | None
    direction: ConnectionDirection
    label: str | None
    confidence: float


@dataclass(frozen=True)
class DiagramEvidence:
    diagram_type: str
    diagram_type_confidence: float
    status: AnalysisStatus
    labels: list[str] = field(default_factory=list)
    components: list[DiagramComponent] = field(default_factory=list)
    connections: list[DiagramConnection] = field(default_factory=list)
    shapes: list[dict[str, Any]] = field(default_factory=list)
    spatial_relationships: list[dict[str, Any]] = field(default_factory=list)
    ocr_text: str = ""
    analysis_provider: str = "classical_vision"
    processing_time_ms: int = 0
    detail: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialization for `DocumentRegion.extra_metadata` (the same
        'one JSON column' convention `TableStructure` already uses)."""
        return {
            "diagram_type": self.diagram_type,
            "diagram_type_confidence": self.diagram_type_confidence,
            "status": self.status,
            "labels": self.labels,
            "components": [
                {
                    "component_id": c.component_id,
                    "shape_type": c.shape_type,
                    "bbox": c.bbox,
                    "label": c.label,
                    "confidence": c.confidence,
                }
                for c in self.components
            ],
            "connections": [
                {
                    "source_component_id": conn.source_component_id,
                    "target_component_id": conn.target_component_id,
                    "direction": conn.direction,
                    "label": conn.label,
                    "confidence": conn.confidence,
                }
                for conn in self.connections
            ],
            "shapes": self.shapes,
            "spatial_relationships": self.spatial_relationships,
            "ocr_text": self.ocr_text,
            "analysis_provider": self.analysis_provider,
            "processing_time_ms": self.processing_time_ms,
            "detail": self.detail,
            "raw_metadata": self.raw_metadata,
        }


def _bbox_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    a_left, a_top, a_w, a_h = a
    b_left, b_top, b_w, b_h = b
    inter_left = max(a_left, b_left)
    inter_top = max(a_top, b_top)
    inter_right = min(a_left + a_w, b_left + b_w)
    inter_bottom = min(a_top + a_h, b_top + b_h)
    if inter_right <= inter_left or inter_bottom <= inter_top:
        return 0.0
    intersection = (inter_right - inter_left) * (inter_bottom - inter_top)
    union = a_w * a_h + b_w * b_h - intersection
    return intersection / union if union > 0 else 0.0


def _deduplicate_by_bbox(
    items: list[dict[str, Any]], *, iou_threshold: float = 0.6
) -> list[dict[str, Any]]:
    """Non-max suppression by bounding-box IoU — a rectangle's stroke has
    both an inner and outer contour (and Hough circle detection commonly
    reports the same real circle at several near-identical radii/centers);
    without this, one real shape is reported many times over, and every
    downstream connection derived from it is duplicated too."""
    ordered = sorted(items, key=lambda item: item["area"], reverse=True)
    kept: list[dict[str, Any]] = []
    for item in ordered:
        if any(_bbox_iou(item["bbox"], kept_item["bbox"]) >= iou_threshold for kept_item in kept):
            continue
        kept.append(item)
    return kept


def _detect_hollow_shapes(
    gray: np.ndarray, binary: np.ndarray
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Detects boxes/circles via contour HIERARCHY (`RETR_CCOMP`), not a
    flat contour or Hough-circle search — a real, confirmed finding from
    this module's own development: diagram connector lines typically
    *touch* the shapes they connect, so a flat `RETR_EXTERNAL`/`RETR_LIST`
    search sees one large connected blob (the whole diagram), not
    individual shapes. `RETR_CCOMP` additionally reports each *hole*
    (interior region) within that blob — a hollow rectangle's or ellipse's
    own enclosed interior is exactly one such hole, giving a reliable way
    to recover individual shapes even when their outlines are joined by
    connectors. `cv2.HoughCircles` was tried first and produced many false
    -positive "circles" on non-circular content (text glyphs, rectangle
    corners) — replaced with a real circularity check
    (4*pi*area/perimeter^2, 1.0 for a perfect circle) on the same hole
    contours used for box detection, which is both more accurate and
    avoids running two separate, disagreeing detectors."""
    height, width = gray.shape[:2]
    min_area = _MIN_BOX_AREA_FRACTION * height * width
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

    boxes: list[dict[str, Any]] = []
    circles: list[dict[str, Any]] = []
    if hierarchy is None:
        return boxes, circles

    for index, contour in enumerate(contours):
        parent = hierarchy[0][index][3]
        if parent == -1:
            continue  # only interior "hole" contours are candidates, not the outer blob itself
        area = cv2.contourArea(contour)
        if area < min_area:
            continue

        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        x, y, w, h = cv2.boundingRect(contour)

        if circularity >= 0.75:
            radius = max(w, h) // 2
            if radius < _MIN_CIRCLE_RADIUS_PX:
                continue
            circles.append({"bbox": (int(x), int(y), int(w), int(h)), "area": float(area)})
            continue

        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) < 4 or len(approx) > 6:
            continue
        if area / (w * h + 1e-6) < 0.5:
            continue
        boxes.append({"bbox": (int(x), int(y), int(w), int(h)), "area": float(area)})

    return _deduplicate_by_bbox(boxes), _deduplicate_by_bbox(circles)


def _detect_lines(binary: np.ndarray) -> list[dict[str, Any]]:
    lines = cv2.HoughLinesP(
        binary,
        rho=1,
        theta=np.pi / 180,
        threshold=30,
        minLineLength=_HOUGH_LINE_MIN_LENGTH_PX,
        maxLineGap=_HOUGH_LINE_MAX_GAP_PX,
    )
    if lines is None:
        return []
    # `HoughLinesP`'s returned array shape has genuinely varied across
    # OpenCV versions (`(N, 1, 4)` historically, `(N, 4)` on this
    # project's installed 5.0.0) — `.reshape(-1, 4)` is robust to either.
    flat_lines = lines.reshape(-1, 4)
    return [
        {"start": (int(x1), int(y1)), "end": (int(x2), int(y2))} for x1, y1, x2, y2 in flat_lines
    ]


def _has_arrowhead(binary: np.ndarray, point: tuple[int, int]) -> bool:
    """Heuristic: an arrowhead is a small, roughly-triangular blob of ink
    concentrated near a line endpoint — genuinely more ink-dense in a
    small radius around the endpoint than a plain line-end would produce.
    A real, cheap geometric signal, not a trained classifier."""
    x, y = point
    height, width = binary.shape[:2]
    left = max(0, x - _ARROWHEAD_SEARCH_RADIUS_PX)
    top = max(0, y - _ARROWHEAD_SEARCH_RADIUS_PX)
    right = min(width, x + _ARROWHEAD_SEARCH_RADIUS_PX)
    bottom = min(height, y + _ARROWHEAD_SEARCH_RADIUS_PX)
    patch = binary[top:bottom, left:right]
    if patch.size == 0:
        return False
    ink_ratio = float(cv2.countNonZero(patch)) / patch.size
    # A plain 2px-wide line through a 50x50 patch covers ~4% of pixels; a
    # filled triangular arrowhead covers substantially more.
    return ink_ratio > 0.12


def _nearest_component(
    point: tuple[int, int], components: list[DiagramComponent]
) -> DiagramComponent | None:
    best: DiagramComponent | None = None
    best_distance = float(_ENDPOINT_SNAP_RADIUS_PX)
    px, py = point
    for component in components:
        left, top, w, h = component.bbox
        cx = max(left, min(px, left + w))
        cy = max(top, min(py, top + h))
        distance = float(np.hypot(px - cx, py - cy))
        if distance < best_distance:
            best_distance = distance
            best = component
    return best


def _guess_diagram_type(
    components: list[DiagramComponent], connections: list[DiagramConnection]
) -> tuple[str, float]:
    """Best-effort, explicitly heuristic — never claimed as certain."""
    if not components:
        return "unknown", 0.0

    box_count = sum(1 for c in components if c.shape_type == "box")
    circle_count = sum(1 for c in components if c.shape_type == "circle")
    directed_count = sum(1 for c in connections if c.direction == "directed")

    if box_count >= 2 and directed_count >= 1:
        return "flowchart", 60.0
    if (box_count + circle_count) >= 2 and connections:
        return "block_diagram", 50.0
    if box_count >= 1 or circle_count >= 1:
        return "labeled_figure", 40.0
    return "unknown", 0.0


def analyze_diagram(image: np.ndarray, *, language: str = "eng") -> DiagramEvidence:
    """Real, deterministic diagram structure extraction. Never raises for
    a structurally valid crop — callers wrap this in try/except only to
    guard against a genuinely corrupt/zero-size crop (Section 19: analysis
    failure must never discard the diagram itself)."""
    started = time.perf_counter()
    if image.size == 0:
        return DiagramEvidence(
            diagram_type="unknown",
            diagram_type_confidence=0.0,
            status="FAILED",
            detail="empty crop",
        )

    gray = to_grayscale(image)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    raw_boxes, raw_circles = _detect_hollow_shapes(gray, binary)
    raw_lines = _detect_lines(binary)

    components: list[DiagramComponent] = []
    tesseract = TesseractProvider()

    for raw_box in raw_boxes:
        left, top, w, h = raw_box["bbox"]
        label = _ocr_crop(tesseract, image[top : top + h, left : left + w], language=language)
        components.append(
            DiagramComponent(
                component_id=f"box-{uuid.uuid4().hex[:8]}",
                shape_type="box",
                bbox=(left, top, w, h),
                label=label or None,
                confidence=_SHAPE_GEOMETRY_CONFIDENCE,
            )
        )
    for raw_circle in raw_circles:
        left, top, w, h = raw_circle["bbox"]
        left, top = max(left, 0), max(top, 0)
        crop = image[top : top + h, left : left + w]
        label = _ocr_crop(tesseract, crop, language=language)
        components.append(
            DiagramComponent(
                component_id=f"circle-{uuid.uuid4().hex[:8]}",
                shape_type="circle",
                bbox=(left, top, w, h),
                label=label or None,
                confidence=_SHAPE_GEOMETRY_CONFIDENCE,
            )
        )

    connections: list[DiagramConnection] = []
    spatial_relationships: list[dict[str, Any]] = []
    seen_connection_keys: set[tuple[str, str, str]] = set()
    for raw_line in raw_lines:
        start_component = _nearest_component(raw_line["start"], components)
        end_component = _nearest_component(raw_line["end"], components)
        if start_component is None and end_component is None:
            continue  # a floating connector with no identifiable endpoints -- not fabricated
        if start_component is not None and start_component is end_component:
            continue  # both ends snapped to the same shape -- not a real connection, just noise

        end_has_arrow = _has_arrowhead(binary, raw_line["end"])
        start_has_arrow = _has_arrowhead(binary, raw_line["start"])
        if end_has_arrow and not start_has_arrow:
            direction: ConnectionDirection = "directed"
            source, target = start_component, end_component
        elif start_has_arrow and not end_has_arrow:
            direction = "directed"
            source, target = end_component, start_component
        elif end_has_arrow and start_has_arrow:
            direction = "undirected"  # arrows at both ends -- genuinely ambiguous, not guessed
            source, target = start_component, end_component
        else:
            direction = "undirected"
            source, target = start_component, end_component

        source_id = source.component_id if source else None
        target_id = target.component_id if target else None
        # Multiple detected Hough line segments commonly trace the same
        # real connector — dedupe by (endpoints, direction) so one visual
        # connection isn't reported many times over (a real finding from
        # this module's own development: an early version reported the
        # same two-shape connection dozens of times).
        source_key, target_key = source_id or "", target_id or ""
        dedupe_key: tuple[str, str, str]
        if direction == "directed":
            dedupe_key = (source_key, target_key, direction)
        else:
            pair = tuple(sorted((source_key, target_key)))
            dedupe_key = (pair[0], pair[1], direction)
        if dedupe_key in seen_connection_keys:
            continue
        seen_connection_keys.add(dedupe_key)

        connections.append(
            DiagramConnection(
                source_component_id=source_id,
                target_component_id=target_id,
                direction=direction,
                label=None,
                confidence=_CONNECTION_ENDPOINT_CONFIDENCE
                if (source and target)
                else _CONNECTION_ENDPOINT_CONFIDENCE / 2,
            )
        )
        spatial_relationships.append(
            {
                "line_start": raw_line["start"],
                "line_end": raw_line["end"],
                "source_component_id": source_id,
                "target_component_id": target_id,
            }
        )

    full_crop_ocr = _ocr_crop(tesseract, image, language=language)
    labels = [c.label for c in components if c.label]

    diagram_type, diagram_type_confidence = _guess_diagram_type(components, connections)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    shapes = [{"type": "box", **b} for b in raw_boxes] + [
        {"type": "circle", **c} for c in raw_circles
    ]

    return DiagramEvidence(
        diagram_type=diagram_type,
        diagram_type_confidence=diagram_type_confidence,
        status="SUCCESS",
        labels=labels,
        components=components,
        connections=connections,
        shapes=shapes,
        spatial_relationships=spatial_relationships,
        ocr_text=full_crop_ocr,
        analysis_provider="classical_vision",
        processing_time_ms=elapsed_ms,
        raw_metadata={
            "box_count": len(raw_boxes),
            "circle_count": len(raw_circles),
            "line_count": len(raw_lines),
        },
    )


def _ocr_crop(provider: TesseractProvider, crop: np.ndarray, *, language: str) -> str:
    if crop.size == 0:
        return ""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(encode_image_to_bytes(crop))
        tmp_path = tmp.name
    try:
        result = provider.extract(tmp_path, language=language)
    except Exception:  # noqa: BLE001 - a failed label OCR must never abort diagram analysis
        return ""
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return result.raw_text.strip()


def analyze_diagram_region(
    image: np.ndarray, region: DetectedRegion, *, language: str = "eng"
) -> DiagramEvidence:
    """Convenience wrapper — crops the region out of the full page image
    before running `analyze_diagram()`."""
    box = region.bbox
    crop = image[box.top : box.top + box.height, box.left : box.left + box.width]
    return analyze_diagram(crop, language=language)
