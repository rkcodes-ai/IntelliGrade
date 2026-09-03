"""
Tests for `PaddleOCRProvider`'s isolated-runtime bridge (Surya/docTR/TrOCR
milestone, Section 16: re-investigating whether the same bridge pattern
makes the pre-existing `.venv-paddleocr` operational). Same two-layer
pattern as `test_ocr_provider_doctr.py`: mocked normalization/failure
tests that always run, plus a real end-to-end integration test gated on
`.venv-paddleocr` existing on this machine.

`test_ocr_providers.py` still covers `PaddleOCRProvider`'s general
contract (is_implemented, health-check-never-crashes, etc.) alongside the
other five original providers — this file is specifically about the new
bridge plumbing this milestone added.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

from app.services.ocr.exceptions import OCRIsolatedRuntimeInferenceError
from app.services.ocr.isolated_runtime import IsolatedRuntimeResult
from app.services.ocr.providers.paddleocr_provider import PaddleOCRProvider

_PADDLEOCR_PYTHON = (
    Path(__file__).resolve().parents[1] / ".venv-paddleocr" / "Scripts" / "python.exe"
)
_requires_real_paddleocr = pytest.mark.skipif(
    not _PADDLEOCR_PYTHON.exists(),
    reason="isolated .venv-paddleocr runtime not present on this machine",
)

_FAKE_SUCCESS_PAYLOAD = {
    "success": True,
    "raw_text": "hello world",
    "average_confidence": 99.1,
    "processing_time_ms": 200,
    "provider_version": "3.7.0",
    "blocks": [
        {
            "bbox": {"left": 0, "top": 0, "width": 100, "height": 20},
            "confidence": 99.1,
            "lines": [
                {
                    "text": "hello world",
                    "bbox": {"left": 0, "top": 0, "width": 100, "height": 20},
                    "confidence": 99.1,
                    "words": [
                        {
                            "text": "hello",
                            "bbox": {"left": 0, "top": 0, "width": 50, "height": 20},
                            "confidence": 99.1,
                        },
                        {
                            "text": "world",
                            "bbox": {"left": 0, "top": 0, "width": 50, "height": 20},
                            "confidence": 99.1,
                        },
                    ],
                }
            ],
        }
    ],
}


def test_extract_normalizes_runner_payload_into_page_result() -> None:
    adapter = PaddleOCRProvider()
    with patch(
        "app.services.ocr.providers.paddleocr_provider.invoke_isolated_runtime",
        return_value=IsolatedRuntimeResult(_FAKE_SUCCESS_PAYLOAD),
    ):
        result = adapter.extract("/fake/path.png", language="eng")

    assert result.raw_text == "hello world"
    assert result.average_confidence == 99.1
    assert len(result.blocks) == 1
    assert result.blocks[0].lines[0].words[1].text == "world"


def test_extract_raises_inference_error_on_success_false() -> None:
    adapter = PaddleOCRProvider()
    fake_error = {"success": False, "error": "smart app control blocked dll"}
    with (
        patch(
            "app.services.ocr.providers.paddleocr_provider.invoke_isolated_runtime",
            return_value=IsolatedRuntimeResult(fake_error),
        ),
        pytest.raises(OCRIsolatedRuntimeInferenceError, match="smart app control"),
    ):
        adapter.extract("/fake/path.png")


def test_health_check_reports_not_ready_when_venv_missing() -> None:
    adapter = PaddleOCRProvider(python_exe=str(Path("/definitely/does/not/exist/python.exe")))
    health = adapter.health_check()
    assert health.installed is False
    assert health.ready is False
    assert "not found" in (health.detail or "")


def test_health_check_never_raises_on_unexpected_runner_error() -> None:
    adapter = PaddleOCRProvider()
    with patch(
        "app.services.ocr.providers.paddleocr_provider.invoke_isolated_runtime",
        side_effect=RuntimeError("boom"),
    ):
        health = adapter.health_check()
    assert health.ready is False
    assert "boom" in (health.detail or "")


@_requires_real_paddleocr
def test_real_paddleocr_extract_against_rendered_image(tmp_path) -> None:
    """Genuine end-to-end proof: real subprocess into `.venv-paddleocr`,
    real `PaddleOCR().predict()`, real recognized text — not a mock, and
    crucially: invoked from the MAIN venv's process, the exact scenario
    Windows Smart App Control previously blocked when attempted in-process."""
    image = Image.new("RGB", (500, 100), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((10, 30), "REAL PADDLEOCR TEST", fill="black")
    path = tmp_path / "paddleocr_real.png"
    image.save(path)

    adapter = PaddleOCRProvider()
    result = adapter.extract(str(path), language="eng")

    assert result.raw_text.strip() != ""
    assert 0.0 <= result.average_confidence <= 100.0
    assert len(result.blocks) >= 1
