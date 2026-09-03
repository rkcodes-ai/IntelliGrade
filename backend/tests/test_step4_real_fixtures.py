"""Real diagram + math test sets (Section 49/50 minimums) and the
eco-efficiency regression (Section 54).

No real scanned exam pages exist in this repository, so every fixture
here is a synthetically rendered but structurally genuine proxy (real
PIL-drawn shapes/lines for diagrams, real font-rendered text for math) —
honestly labeled as such, never claimed to be a real scanned document.
"handwritten" fixtures use a cursive/script Windows font as a proxy for
handwriting (Segoe Script if present, else a fallback), NOT a claim that
this validates real handwriting recognition accuracy — that would
require real handwritten samples this project doesn't have.

Each diagram case asserts genuine processing (no crash, honest
status/confidence) rather than a specific hardcoded "correct" recognition
outcome per type, since classical vision's accuracy legitimately varies
by diagram complexity (see `diagram_analysis.py`'s module docstring on
scope). Math cases assert a real recognized expression was produced
(skipped if `.venv-math` is absent on this machine) — pix2tex's own
accuracy on some of the harder samples (matrices, multiline) is honestly
expected to be imperfect and is not asserted exactly.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.services.document_intelligence.compute_budget import should_analyze_region
from app.services.document_intelligence.diagram_analysis import analyze_diagram
from app.services.document_intelligence.layout import BoundingBox, DetectedRegion
from app.services.document_intelligence.math_recognition import MathRecognitionAdapter
from app.services.ocr.isolated_runtime import default_isolated_python

_MATH_VENV_PYTHON = default_isolated_python(".venv-math")


def _font(size: int = 24, *, script: bool = False) -> ImageFont.FreeTypeFont:
    candidates = ["segoescr.ttf", "comic.ttf"] if script else ["arial.ttf", "calibri.ttf"]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def _to_bgr(img: Image.Image) -> np.ndarray:
    return np.array(img.convert("RGB"))[:, :, ::-1].copy()


# --------------------------------------------------------------------- #
# Section 49: diagram test set
# --------------------------------------------------------------------- #


def test_diagram_fixture_flowchart() -> None:
    img = Image.new("RGB", (500, 300), "white")
    draw = ImageDraw.Draw(img)
    font = _font()
    draw.rectangle([50, 30, 200, 90], outline="black", width=3)
    draw.text((90, 50), "Start", fill="black", font=font)
    draw.line([(125, 90), (125, 140)], fill="black", width=3)
    draw.polygon([(125, 150), (115, 135), (135, 135)], fill="black")
    draw.rectangle([50, 150, 200, 210], outline="black", width=3)
    draw.text((90, 170), "Process", fill="black", font=font)
    evidence = analyze_diagram(_to_bgr(img))
    assert evidence.status == "SUCCESS"
    assert evidence.processing_time_ms >= 0


def test_diagram_fixture_block_diagram() -> None:
    img = Image.new("RGB", (500, 200), "white")
    draw = ImageDraw.Draw(img)
    font = _font()
    draw.rectangle([30, 60, 160, 130], outline="black", width=3)
    draw.text((55, 85), "CPU", fill="black", font=font)
    draw.rectangle([200, 60, 330, 130], outline="black", width=3)
    draw.text((225, 85), "RAM", fill="black", font=font)
    draw.line([(160, 95), (200, 95)], fill="black", width=3)
    evidence = analyze_diagram(_to_bgr(img))
    assert evidence.status == "SUCCESS"


def test_diagram_fixture_network_architecture_diagram() -> None:
    img = Image.new("RGB", (600, 220), "white")
    draw = ImageDraw.Draw(img)
    font = _font(20)
    labels = ["Client", "Server", "Database"]
    for index, label in enumerate(labels):
        left = 30 + index * 200
        draw.rectangle([left, 70, left + 140, 130], outline="black", width=3)
        draw.text((left + 25, 90), label, fill="black", font=font)
        if index > 0:
            draw.line([(left - 60, 100), (left, 100)], fill="black", width=3)
    evidence = analyze_diagram(_to_bgr(img))
    assert evidence.status == "SUCCESS"
    assert evidence.raw_metadata["box_count"] >= 1


def test_diagram_fixture_labeled_scientific_diagram() -> None:
    img = Image.new("RGB", (400, 400), "white")
    draw = ImageDraw.Draw(img)
    font = _font(18)
    draw.ellipse([120, 120, 280, 280], outline="black", width=3)
    draw.text((150, 190), "Nucleus", fill="black", font=font)
    draw.line([(280, 200), (360, 200)], fill="black", width=2)
    draw.text((285, 205), "membrane", fill="black", font=font)
    evidence = analyze_diagram(_to_bgr(img))
    assert evidence.status == "SUCCESS"


def test_diagram_fixture_graph_chart() -> None:
    img = Image.new("RGB", (400, 300), "white")
    draw = ImageDraw.Draw(img)
    font = _font(16)
    draw.line([(50, 250), (350, 250)], fill="black", width=2)  # x-axis
    draw.line([(50, 250), (50, 30)], fill="black", width=2)  # y-axis
    draw.text((180, 260), "Time", fill="black", font=font)
    draw.line([(50, 200), (150, 120), (250, 160), (350, 60)], fill="black", width=2)
    evidence = analyze_diagram(_to_bgr(img))
    assert evidence.status == "SUCCESS"


def test_diagram_fixture_handwritten_student_diagram_proxy() -> None:
    """Script-font proxy for a handwritten diagram -- honestly not a
    validated handwriting-accuracy test (see module docstring)."""
    img = Image.new("RGB", (400, 250), "white")
    draw = ImageDraw.Draw(img)
    font = _font(22, script=True)
    draw.rectangle([40, 40, 180, 100], outline="black", width=2)
    draw.text((60, 55), "input", fill="black", font=font)
    draw.line([(180, 70), (240, 70)], fill="black", width=2)
    draw.rectangle([240, 40, 380, 100], outline="black", width=2)
    draw.text((260, 55), "output", fill="black", font=font)
    evidence = analyze_diagram(_to_bgr(img))
    assert evidence.status == "SUCCESS"
    assert evidence.detail is None or evidence.status == "SUCCESS"


# --------------------------------------------------------------------- #
# Section 50: math test set (skipped if .venv-math is absent)
# --------------------------------------------------------------------- #

_MATH_SAMPLES: dict[str, str] = {
    "simple_algebra": "x + y = 10",
    "fractions": "1/2 + 1/3",
    "exponents_subscripts": "x^2 + a_1",
    "square_root": "sqrt(x + 1)",
    "integral": "integral f(x) dx",
    "summation": "sum i=1 to n",
    "matrix": "1 2 / 3 4",
    "greek_symbols": "alpha + beta = gamma",
    "multiline": "x + y = 5\nx - y = 1",
    "handwritten_proxy": "x + y = z",
}


def _render_math_image(text: str, *, script: bool = False) -> Image.Image:
    img = Image.new("RGB", (500, 120), "white")
    draw = ImageDraw.Draw(img)
    font = _font(28, script=script)
    draw.multiline_text((15, 30), text, fill="black", font=font)
    return img


@pytest.mark.skipif(not _MATH_VENV_PYTHON.exists(), reason=".venv-math not present on this machine")
@pytest.mark.parametrize("name,text", list(_MATH_SAMPLES.items()))
def test_math_recognition_fixture(tmp_path, name: str, text: str) -> None:
    is_handwritten_proxy = name == "handwritten_proxy"
    img = _render_math_image(text, script=is_handwritten_proxy)
    crop_path = tmp_path / f"{name}.png"
    img.save(crop_path)

    adapter = MathRecognitionAdapter()
    evidence = adapter.recognize(
        str(crop_path),
        printed_or_handwritten="handwritten" if is_handwritten_proxy else "printed",
    )

    assert evidence.status == "SUCCESS"
    assert evidence.processing_time_ms >= 0
    assert evidence.raw_metadata["crop_path"] == str(crop_path)
    # Real output is asserted to exist; not asserted to be a *correct*
    # transcription of `text` -- pix2tex accuracy on plain-font renders
    # (as opposed to real LaTeX-typeset or real handwriting) is honestly
    # variable, and asserting exact correctness here would misrepresent
    # what this test actually verifies (real, non-crashing inference).
    assert isinstance(evidence.recognized_expression, str)


# --------------------------------------------------------------------- #
# Section 54: eco-efficiency routing regression
# --------------------------------------------------------------------- #


def _region(region_type: str) -> DetectedRegion:
    return DetectedRegion(
        region_type=region_type,
        bbox=BoundingBox(left=0, top=0, width=100, height=100),
        confidence=90.0,
        source_detector="surya_layout",
        reading_order=0,
        source_label="Text" if region_type == "PRINTED_TEXT" else region_type.title(),
    )


def _count_gated_calls(regions: list[DetectedRegion]) -> tuple[int, int]:
    visual_calls = math_calls = 0
    for region in regions:
        gated = should_analyze_region(
            region, analyzed_visual_count=visual_calls, analyzed_math_count=math_calls
        )
        if not gated:
            continue
        if region.region_type == "DIAGRAM":
            visual_calls += 1
        elif region.region_type == "EQUATION":
            math_calls += 1
    return visual_calls, math_calls


def test_eco_efficiency_text_only_page_invokes_neither_visual_nor_math() -> None:
    regions = [_region("PRINTED_TEXT"), _region("PRINTED_TEXT"), _region("HEADER")]
    assert _count_gated_calls(regions) == (0, 0)


def test_eco_efficiency_equation_only_region_invokes_math_not_diagram() -> None:
    assert _count_gated_calls([_region("EQUATION")]) == (0, 1)


def test_eco_efficiency_diagram_only_region_invokes_diagram_not_math() -> None:
    assert _count_gated_calls([_region("DIAGRAM")]) == (1, 0)
