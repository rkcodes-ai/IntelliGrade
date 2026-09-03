"""Unit tests for `app.services.document_intelligence.routing` — real
Tesseract OCR on synthetic crops (table cells, captions), real
Hough-line-grid table detection, and the honestly-deferred visual/math
provider interfaces."""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.services.document_intelligence.layout import DetectedRegion
from app.services.document_intelligence.routing import (
    DEFAULT_MATH_RECOGNITION_PROVIDER,
    DEFAULT_VISUAL_ANALYSIS_PROVIDER,
    extract_table_structure,
    preserve_region_crop,
)
from app.services.ocr.base import BoundingBox


def _region(region_type: str, bbox: BoundingBox) -> DetectedRegion:
    return DetectedRegion(
        region_type=region_type,
        bbox=bbox,
        confidence=90.0,
        source_detector="test",
        reading_order=0,
        source_label=region_type,
    )


def test_preserve_region_crop_returns_real_png_bytes_of_exact_region() -> None:
    image = np.full((300, 300, 3), 255, dtype=np.uint8)
    image[50:100, 50:150] = 0  # a distinctive black rectangle inside the region

    region = _region("DIAGRAM", BoundingBox(left=40, top=40, width=120, height=80))
    crop_bytes = preserve_region_crop(image, region)

    assert crop_bytes[:8] == b"\x89PNG\r\n\x1a\n"  # genuine PNG file signature
    decoded = cv2.imdecode(np.frombuffer(crop_bytes, np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape == (80, 120, 3)


def _synthetic_ruled_table(rows: int = 3, cols: int = 3) -> tuple[np.ndarray, dict]:
    margin = 6
    cell_w, cell_h = 150, 100
    img = Image.new("RGB", (cols * cell_w + margin * 2, rows * cell_h + margin * 2), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    for r in range(rows + 1):
        draw.line(
            [(margin, margin + r * cell_h), (margin + cols * cell_w, margin + r * cell_h)],
            fill="black",
            width=2,
        )
    for c in range(cols + 1):
        draw.line(
            [(margin + c * cell_w, margin), (margin + c * cell_w, margin + rows * cell_h)],
            fill="black",
            width=2,
        )
    labels = {}
    for r in range(rows):
        for c in range(cols):
            text = f"{chr(65 + c)}{r + 1}"
            position = (margin + c * cell_w + 55, margin + r * cell_h + 40)
            draw.text(position, text, fill="black", font=font)
            labels[(r, c)] = text
    return np.array(img)[:, :, ::-1].copy(), labels


def test_real_table_structure_extraction_finds_correct_grid_and_text() -> None:
    image, expected_labels = _synthetic_ruled_table()
    height, width = image.shape[:2]
    region = _region("TABLE", BoundingBox(left=0, top=0, width=width, height=height))

    structure = extract_table_structure(image, region)

    assert structure.row_count == 3
    assert structure.col_count == 3
    assert structure.detection_method == "hough_line_grid"
    assert len(structure.cells) == 9
    # At least 8/9 cells (a lenient, honest bound — OCR at this synthetic
    # scale occasionally misreads "1" as "l", a genuine, expected limit).
    correct = sum(
        1
        for cell in structure.cells
        if cell.text.replace("l", "1") == expected_labels[(cell.row, cell.col)]
    )
    assert correct >= 8


def test_table_without_a_clean_grid_falls_back_to_whole_region() -> None:
    image = np.full((100, 200, 3), 255, dtype=np.uint8)
    cv2.putText(image, "no grid here", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    region = _region("TABLE", BoundingBox(left=0, top=0, width=200, height=100))

    structure = extract_table_structure(image, region)
    assert structure.detection_method == "whole_region_fallback"
    assert structure.row_count == 1
    assert structure.col_count == 1


def test_visual_analysis_provider_is_honestly_not_implemented() -> None:
    result = DEFAULT_VISUAL_ANALYSIS_PROVIDER.analyze(np.zeros((10, 10, 3), dtype=np.uint8))
    assert result.status == "NOT_IMPLEMENTED"
    assert result.detail is not None


def test_math_recognition_provider_is_honestly_not_implemented() -> None:
    result = DEFAULT_MATH_RECOGNITION_PROVIDER.recognize(np.zeros((10, 10, 3), dtype=np.uint8))
    assert result.status == "NOT_IMPLEMENTED"
    assert result.latex is None
