"""Tests for `SuryaOCRAdapter` — same two-layer pattern as
`test_ocr_provider_doctr.py`: mocked normalization/failure-handling tests
that always run, plus a real-integration test gated on `.venv-surya`
actually existing on this machine."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

from app.services.ocr.exceptions import OCRIsolatedRuntimeInferenceError
from app.services.ocr.isolated_runtime import IsolatedRuntimeResult
from app.services.ocr.providers.surya_provider import SuryaOCRAdapter

_SURYA_PYTHON = Path(__file__).resolve().parents[1] / ".venv-surya" / "Scripts" / "python.exe"
_requires_real_surya = pytest.mark.skipif(
    not _SURYA_PYTHON.exists(),
    reason="isolated .venv-surya runtime not present on this machine",
)

_FAKE_SUCCESS_PAYLOAD = {
    "success": True,
    "raw_text": "hello world",
    "average_confidence": 93.0,
    "processing_time_ms": 50,
    "provider_version": "0.13.1",
    "blocks": [
        {
            "bbox": {"left": 0, "top": 0, "width": 100, "height": 20},
            "confidence": 93.0,
            "lines": [
                {
                    "text": "hello world",
                    "bbox": {"left": 0, "top": 0, "width": 100, "height": 20},
                    "confidence": 93.0,
                    "words": [
                        {
                            "text": "hello",
                            "bbox": {"left": 0, "top": 0, "width": 50, "height": 20},
                            "confidence": 93.0,
                        },
                        {
                            "text": "world",
                            "bbox": {"left": 0, "top": 0, "width": 50, "height": 20},
                            "confidence": 93.0,
                        },
                    ],
                }
            ],
        }
    ],
}


def test_extract_normalizes_runner_payload_into_page_result() -> None:
    adapter = SuryaOCRAdapter()
    with patch(
        "app.services.ocr.providers.surya_provider.invoke_isolated_runtime",
        return_value=IsolatedRuntimeResult(_FAKE_SUCCESS_PAYLOAD),
    ):
        result = adapter.extract("/fake/path.png", language="eng")

    assert result.raw_text == "hello world"
    assert result.average_confidence == 93.0
    assert len(result.blocks) == 1
    assert len(result.blocks[0].lines) == 1
    assert result.blocks[0].lines[0].words[0].text == "hello"


def test_extract_raises_inference_error_on_success_false() -> None:
    adapter = SuryaOCRAdapter()
    with patch(
        "app.services.ocr.providers.surya_provider.invoke_isolated_runtime",
        return_value=IsolatedRuntimeResult({"success": False, "error": "docker binary not found"}),
    ), pytest.raises(OCRIsolatedRuntimeInferenceError, match="docker binary not found"):
        adapter.extract("/fake/path.png")


def test_health_check_reports_not_ready_when_venv_missing() -> None:
    adapter = SuryaOCRAdapter(python_exe=str(Path("/definitely/does/not/exist/python.exe")))
    health = adapter.health_check()
    assert health.installed is False
    assert health.ready is False
    assert "not found" in (health.detail or "")


def test_health_check_never_raises_on_unexpected_runner_error() -> None:
    adapter = SuryaOCRAdapter()
    with patch(
        "app.services.ocr.providers.surya_provider.invoke_isolated_runtime",
        side_effect=RuntimeError("boom"),
    ):
        health = adapter.health_check()
    assert health.ready is False
    assert "boom" in (health.detail or "")


@_requires_real_surya
def test_real_surya_extract_against_rendered_image(tmp_path) -> None:
    """Genuine end-to-end proof: real subprocess into `.venv-surya`, real
    `surya-ocr==0.13.1` DetectionPredictor + RecognitionPredictor, real
    recognized text — not a mock."""
    image = Image.new("RGB", (500, 100), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((10, 30), "REAL SURYA TEST", fill="black")
    path = tmp_path / "surya_real.png"
    image.save(path)

    adapter = SuryaOCRAdapter()
    result = adapter.extract(str(path), language="eng")

    assert result.raw_text.strip() != ""
    assert 0.0 <= result.average_confidence <= 100.0
    assert len(result.blocks) >= 1
