"""Tests for `TrOCRHandwrittenAdapter` — the detect (via EasyOCR) -> crop
-> recognize (isolated `.venv-trocr`) -> reconstruct pipeline. Same
two-layer pattern as the docTR/Surya adapter tests: mocked
normalization/failure-handling tests that always run, plus a real
end-to-end integration test (real EasyOCR line detection AND real TrOCR
recognition) gated on `.venv-trocr` actually existing on this machine."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

from app.services.ocr.base import BoundingBox, OCRBlockResult, OCRLineResult, OCRPageResult
from app.services.ocr.exceptions import OCRIsolatedRuntimeInferenceError
from app.services.ocr.isolated_runtime import IsolatedRuntimeResult
from app.services.ocr.providers.trocr_provider import TrOCRHandwrittenAdapter

_TROCR_PYTHON = Path(__file__).resolve().parents[1] / ".venv-trocr" / "Scripts" / "python.exe"
_requires_real_trocr = pytest.mark.skipif(
    not _TROCR_PYTHON.exists(),
    reason="isolated .venv-trocr runtime not present on this machine",
)


class _FakeDetector:
    """Stands in for EasyOCRProvider — returns two fixed line boxes,
    isolating these tests from EasyOCR's own model weights."""

    def extract(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
        line1 = OCRLineResult(
            text="ignored-detector-text-1",
            bounding_box=BoundingBox(left=0, top=0, width=100, height=20),
            confidence=80.0,
            reading_order=0,
        )
        line2 = OCRLineResult(
            text="ignored-detector-text-2",
            bounding_box=BoundingBox(left=0, top=30, width=100, height=20),
            confidence=80.0,
            reading_order=1,
        )
        block = OCRBlockResult(
            bounding_box=BoundingBox(left=0, top=0, width=100, height=50),
            confidence=80.0,
            reading_order=0,
            lines=[line1, line2],
        )
        return OCRPageResult(
            raw_text="ignored",
            average_confidence=80.0,
            language=language,
            rotation_degrees=0.0,
            blocks=[block],
        )


def _make_test_image(tmp_path: Path) -> str:
    image = Image.new("RGB", (200, 60), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((5, 5), "line one", fill="black")
    draw.text((5, 35), "line two", fill="black")
    path = tmp_path / "trocr_fixture.png"
    image.save(path)
    return str(path)


def test_extract_reattaches_recognized_text_to_detector_geometry(tmp_path) -> None:
    adapter = TrOCRHandwrittenAdapter(line_detector=_FakeDetector())
    fake_payload = {
        "success": True,
        "results": [
            {"text": "hello", "confidence": 91.0},
            {"text": "world", "confidence": 88.0},
        ],
    }
    with patch(
        "app.services.ocr.providers.trocr_provider.invoke_isolated_runtime",
        return_value=IsolatedRuntimeResult(fake_payload),
    ):
        result = adapter.extract(_make_test_image(tmp_path), language="eng")

    assert result.raw_text == "hello\nworld"
    lines = result.blocks[0].lines
    assert lines[0].text == "hello"
    assert lines[0].bounding_box == BoundingBox(left=0, top=0, width=100, height=20)
    assert lines[1].text == "world"
    assert lines[1].confidence == 88.0


def test_extract_raises_inference_error_on_success_false(tmp_path) -> None:
    adapter = TrOCRHandwrittenAdapter(line_detector=_FakeDetector())
    with patch(
        "app.services.ocr.providers.trocr_provider.invoke_isolated_runtime",
        return_value=IsolatedRuntimeResult({"success": False, "error": "model load failed"}),
    ), pytest.raises(OCRIsolatedRuntimeInferenceError, match="model load failed"):
        adapter.extract(_make_test_image(tmp_path))


def test_extract_returns_empty_result_when_detector_finds_no_lines(tmp_path) -> None:
    class _EmptyDetector:
        def extract(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
            return OCRPageResult(
                raw_text="",
                average_confidence=0.0,
                language=language,
                rotation_degrees=0.0,
                blocks=[],
            )

    adapter = TrOCRHandwrittenAdapter(line_detector=_EmptyDetector())
    result = adapter.extract(_make_test_image(tmp_path))
    assert result.raw_text == ""
    assert result.blocks == []


def test_health_check_reports_not_ready_when_venv_missing() -> None:
    adapter = TrOCRHandwrittenAdapter(python_exe=str(Path("/definitely/does/not/exist/python.exe")))
    health = adapter.health_check()
    assert health.installed is False
    assert health.ready is False
    assert "not found" in (health.detail or "")


@_requires_real_trocr
def test_real_trocr_pipeline_against_rendered_multiline_image(tmp_path) -> None:
    """Genuine end-to-end proof: real EasyOCR line detection (main venv,
    in-process) + real subprocess into `.venv-trocr` + real
    `VisionEncoderDecoderModel.generate()` recognition per cropped line."""
    image = Image.new("RGB", (500, 120), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((10, 10), "first real line", fill="black")
    draw.text((10, 60), "second real line", fill="black")
    path = tmp_path / "trocr_real.png"
    image.save(path)

    adapter = TrOCRHandwrittenAdapter()
    result = adapter.extract(str(path), language="eng")

    assert result.raw_text.strip() != ""
    assert len(result.blocks) >= 1
    assert len(result.blocks[0].lines) >= 1
    for line in result.blocks[0].lines:
        assert 0.0 <= line.confidence <= 100.0
