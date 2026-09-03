"""Unit tests for `app.services.document_intelligence.layout`.
`reconcile_regions()` is pure geometry (no I/O) and always runs;
`detect_regions_surya()` is a real end-to-end integration test gated on
`.venv-surya` existing on this machine (same pattern as the OCR provider
bridge tests), since it's a real subprocess call, not a mock."""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.services.document_intelligence.layout import (
    DetectedRegion,
    detect_regions_surya,
    reconcile_regions,
)
from app.services.ocr.base import BoundingBox

_SURYA_PYTHON = Path(__file__).resolve().parents[1] / ".venv-surya" / "Scripts" / "python.exe"
_requires_real_surya = pytest.mark.skipif(
    not _SURYA_PYTHON.exists(), reason="isolated .venv-surya runtime not present on this machine"
)


def _region(
    region_type: str, bbox: BoundingBox, confidence: float, source: str, order: int
) -> DetectedRegion:
    return DetectedRegion(
        region_type=region_type,
        bbox=bbox,
        confidence=confidence,
        source_detector=source,
        reading_order=order,
        source_label=region_type,
    )


def test_single_detector_output_is_a_no_op_reordering() -> None:
    regions = [
        _region("PRINTED_TEXT", BoundingBox(0, 0, 100, 20), 90.0, "surya_layout", 0),
        _region("TABLE", BoundingBox(0, 30, 100, 50), 85.0, "surya_layout", 1),
    ]
    reconciled = reconcile_regions([("surya_layout", regions)])
    assert len(reconciled) == 2
    assert [r.region_type for r in reconciled] == ["PRINTED_TEXT", "TABLE"]


def test_overlapping_regions_from_two_detectors_keep_higher_confidence_one() -> None:
    region_a = _region("TABLE", BoundingBox(0, 0, 100, 100), 70.0, "detector_a", 0)
    # near-identical box to region_a
    region_b = _region("DIAGRAM", BoundingBox(5, 5, 95, 95), 95.0, "detector_b", 0)

    reconciled = reconcile_regions([("detector_a", [region_a]), ("detector_b", [region_b])])
    assert len(reconciled) == 1
    assert reconciled[0].region_type == "DIAGRAM"  # the higher-confidence one won
    assert reconciled[0].source_detector == "detector_b"


def test_non_overlapping_regions_from_two_detectors_are_both_kept() -> None:
    region_a = _region("PRINTED_TEXT", BoundingBox(0, 0, 100, 50), 90.0, "detector_a", 0)
    region_b = _region("TABLE", BoundingBox(200, 200, 100, 50), 85.0, "detector_b", 0)

    reconciled = reconcile_regions([("detector_a", [region_a]), ("detector_b", [region_b])])
    assert len(reconciled) == 2


def test_reconciled_regions_get_fresh_sequential_reading_order() -> None:
    region_a = _region("TABLE", BoundingBox(0, 100, 100, 50), 70.0, "detector_a", 5)
    region_b = _region("PRINTED_TEXT", BoundingBox(0, 0, 100, 50), 95.0, "detector_b", 9)

    reconciled = reconcile_regions([("detector_a", [region_a]), ("detector_b", [region_b])])
    assert [r.reading_order for r in reconciled] == [0, 1]
    # sorted top-to-bottom, so the (top=0) region comes first regardless
    # of its original detector's own reading_order value.
    assert reconciled[0].region_type == "PRINTED_TEXT"


@_requires_real_surya
def test_real_surya_layout_detection_against_rendered_page(tmp_path) -> None:
    """Genuine end-to-end proof: real subprocess into `.venv-surya`, real
    `LayoutPredictor`, real detected regions — not a mock."""
    image = Image.new("RGB", (900, 200), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 20), "A representative printed text line", fill="black")
    draw.text((20, 100), "A second representative printed text line", fill="black")
    path = tmp_path / "layout_real.png"
    image.save(path)

    regions = detect_regions_surya(str(path))
    assert len(regions) >= 1
    for region in regions:
        assert region.region_type in (
            "PRINTED_TEXT",
            "HANDWRITTEN_TEXT",
            "HEADER",
            "FOOTER",
            "DIAGRAM",
            "TABLE",
            "EQUATION",
            "OTHER",
        )
        assert 0.0 <= region.confidence <= 100.0
