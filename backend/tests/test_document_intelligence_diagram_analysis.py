"""Unit tests for `app.services.document_intelligence.diagram_analysis` —
real OpenCV geometry + real Tesseract OCR on synthetic diagrams. No
mocking: this module's whole value is genuine deterministic detection."""

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.services.document_intelligence.diagram_analysis import analyze_diagram


def _synthetic_flowchart() -> np.ndarray:
    img = Image.new("RGB", (500, 300), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    draw.rectangle([50, 30, 200, 90], outline="black", width=3)
    draw.text((90, 50), "Start", fill="black", font=font)
    draw.line([(125, 90), (125, 140)], fill="black", width=3)
    draw.polygon([(125, 150), (115, 135), (135, 135)], fill="black")
    draw.rectangle([50, 150, 200, 210], outline="black", width=3)
    draw.text((90, 170), "Process", fill="black", font=font)
    return np.array(img)[:, :, ::-1].copy()


def _blank_image() -> np.ndarray:
    return np.full((200, 300, 3), 255, dtype=np.uint8)


def test_real_flowchart_detects_both_boxes_with_correct_labels() -> None:
    image = _synthetic_flowchart()
    evidence = analyze_diagram(image)

    assert evidence.status == "SUCCESS"
    labels = {c.label for c in evidence.components if c.label}
    assert "Start" in labels
    assert "Process" in labels
    assert all(c.shape_type in ("box", "circle") for c in evidence.components)


def test_real_flowchart_detects_a_connection_between_the_two_boxes() -> None:
    image = _synthetic_flowchart()
    evidence = analyze_diagram(image)

    box_ids = {c.component_id for c in evidence.components}
    real_connections = [
        conn
        for conn in evidence.connections
        if conn.source_component_id in box_ids and conn.target_component_id in box_ids
    ]
    assert len(real_connections) >= 1


def test_no_duplicate_shapes_for_a_single_rectangle() -> None:
    """Regression test for a real bug found during development: a
    rectangle's stroke has both an inner and outer contour, which an
    earlier version of this module double-counted as two shapes."""
    img = Image.new("RGB", (200, 150), color="white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 160, 110], outline="black", width=3)
    image = np.array(img)[:, :, ::-1].copy()

    evidence = analyze_diagram(image)
    boxes = [c for c in evidence.components if c.shape_type == "box"]
    assert len(boxes) == 1


def test_no_self_loop_connections() -> None:
    """Regression test for a real bug: a line whose both endpoints
    snapped to the same shape must never be reported as a connection."""
    image = _synthetic_flowchart()
    evidence = analyze_diagram(image)
    for conn in evidence.connections:
        if conn.source_component_id is not None:
            assert conn.source_component_id != conn.target_component_id


def test_connections_are_deduplicated() -> None:
    image = _synthetic_flowchart()
    evidence = analyze_diagram(image)
    seen = set()
    for conn in evidence.connections:
        key = (conn.source_component_id, conn.target_component_id, conn.direction)
        assert key not in seen
        seen.add(key)


def test_blank_image_produces_no_fabricated_components() -> None:
    evidence = analyze_diagram(_blank_image())
    assert evidence.status == "SUCCESS"
    assert evidence.components == []
    assert evidence.connections == []
    assert evidence.diagram_type == "unknown"


def test_empty_crop_fails_safely_without_raising() -> None:
    evidence = analyze_diagram(np.zeros((0, 0, 3), dtype=np.uint8))
    assert evidence.status == "FAILED"
    assert evidence.detail is not None


def test_flowchart_type_guessed_with_honest_confidence() -> None:
    image = _synthetic_flowchart()
    evidence = analyze_diagram(image)
    assert evidence.diagram_type in ("flowchart", "block_diagram", "labeled_figure")
    assert 0.0 <= evidence.diagram_type_confidence <= 100.0


def test_to_dict_is_fully_json_serializable() -> None:
    import json

    image = _synthetic_flowchart()
    evidence = analyze_diagram(image)
    serialized = json.dumps(evidence.to_dict())
    assert "diagram_type" in serialized
