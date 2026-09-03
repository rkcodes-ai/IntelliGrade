"""
Tests for `DocTROCRAdapter` (Surya/docTR/TrOCR isolated-runtime milestone).

Two layers, per this milestone's brief (Section 25: "targeted tests for
... doctr adapter ... doctr normalization ... doctr failures"):

1. Normalization/failure-handling unit tests that mock
   `invoke_isolated_runtime` — these always run, in every environment,
   since they don't touch the real `.venv-doctr` venv or download any
   model weights.
2. A real-integration test that genuinely calls the isolated `.venv-doctr`
   interpreter and asserts on real docTR inference output — skipped (not
   failed) when that venv doesn't exist on the current machine, since it
   isn't committed to the repository (same reasoning as the pre-existing
   `.venv-paddleocr`-dependent tests elsewhere in this suite).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

from app.services.ocr.exceptions import OCRIsolatedRuntimeInferenceError
from app.services.ocr.isolated_runtime import IsolatedRuntimeResult
from app.services.ocr.providers.doctr_provider import DocTROCRAdapter

_DOCTR_PYTHON = Path(__file__).resolve().parents[1] / ".venv-doctr" / "Scripts" / "python.exe"
_requires_real_doctr = pytest.mark.skipif(
    not _DOCTR_PYTHON.exists(),
    reason="isolated .venv-doctr runtime not present on this machine",
)

_FAKE_SUCCESS_PAYLOAD = {
    "success": True,
    "raw_text": "hello world",
    "average_confidence": 91.5,
    "processing_time_ms": 123,
    "provider_version": "v1.0.1",
    "blocks": [
        {
            "bbox": {"left": 0, "top": 0, "width": 100, "height": 40},
            "confidence": 91.5,
            "lines": [
                {
                    "text": "hello world",
                    "bbox": {"left": 0, "top": 0, "width": 100, "height": 20},
                    "confidence": 91.5,
                    "words": [
                        {
                            "text": "hello",
                            "bbox": {"left": 0, "top": 0, "width": 40, "height": 20},
                            "confidence": 95.0,
                        },
                        {
                            "text": "world",
                            "bbox": {"left": 45, "top": 0, "width": 55, "height": 20},
                            "confidence": 88.0,
                        },
                    ],
                }
            ],
        }
    ],
}


def test_extract_normalizes_runner_payload_into_page_result() -> None:
    adapter = DocTROCRAdapter()
    with patch(
        "app.services.ocr.providers.doctr_provider.invoke_isolated_runtime",
        return_value=IsolatedRuntimeResult(_FAKE_SUCCESS_PAYLOAD),
    ):
        result = adapter.extract("/fake/path.png", language="eng")

    assert result.raw_text == "hello world"
    assert result.average_confidence == 91.5
    assert len(result.blocks) == 1
    block = result.blocks[0]
    assert len(block.lines) == 1
    line = block.lines[0]
    assert line.text == "hello world"
    assert len(line.words) == 2
    assert line.words[0].text == "hello"
    assert line.words[1].confidence == 88.0


def test_extract_raises_inference_error_on_success_false() -> None:
    adapter = DocTROCRAdapter()
    with patch(
        "app.services.ocr.providers.doctr_provider.invoke_isolated_runtime",
        return_value=IsolatedRuntimeResult({"success": False, "error": "corrupt image"}),
    ), pytest.raises(OCRIsolatedRuntimeInferenceError, match="corrupt image"):
        adapter.extract("/fake/path.png")


def test_health_check_reports_not_ready_when_venv_missing() -> None:
    adapter = DocTROCRAdapter(python_exe=str(Path("/definitely/does/not/exist/python.exe")))
    health = adapter.health_check()
    assert health.installed is False
    assert health.ready is False
    assert health.dependencies_ok is False
    assert "not found" in (health.detail or "")


def test_health_check_never_raises_on_unexpected_runner_error() -> None:
    adapter = DocTROCRAdapter()
    with patch(
        "app.services.ocr.providers.doctr_provider.invoke_isolated_runtime",
        side_effect=RuntimeError("boom"),
    ):
        health = adapter.health_check()
    assert health.ready is False
    assert "boom" in (health.detail or "")


@_requires_real_doctr
def test_real_doctr_extract_against_rendered_image(tmp_path) -> None:
    """Genuine end-to-end proof: real subprocess into `.venv-doctr`, real
    `ocr_predictor(pretrained=True)`, real recognized text — not a mock."""
    image = Image.new("RGB", (500, 100), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((10, 30), "REAL DOCTR TEST", fill="black")
    path = tmp_path / "doctr_real.png"
    image.save(path)

    adapter = DocTROCRAdapter()
    result = adapter.extract(str(path), language="eng")

    assert result.raw_text.strip() != ""
    assert 0.0 <= result.average_confidence <= 100.0
    assert len(result.blocks) >= 1
