"""
Runner script executed by `.venv-math`'s interpreter (never imported by
the main backend venv — see `app.services.ocr.isolated_runtime`).

Wraps `pix2tex` (LaTeX-OCR, PyPI package `pix2tex`, MIT licensed — see
`document_intelligence/math_recognition.py`'s module docstring for the
license-verification detail) for image-to-LaTeX math recognition. This
is a single-crop-per-call recognizer, mirroring `trocr_runner.py`'s
one-crop-in, one-result-out shape.

pix2tex's `LatexOCR.__call__` has no native confidence score at all (unlike
TrOCR, which at least exposes per-token logits via `output_scores=True`
in `generate()` — pix2tex's CLI wrapper does not expose an equivalent
hook). Rather than fabricate a number, this runner reports a fixed,
explicitly-labelled placeholder confidence of 50.0 ("unknown / not
measured" — deliberately the neutral midpoint, never a high number that
would misrepresent certainty) and documents this honestly wherever the
result is surfaced. Any future work that finds a real per-token or
per-sequence probability signal in pix2tex's internals should replace
this rather than repurpose the placeholder.

Request: `{"crop": str, "options": {}}`.
Response (`success: true`): `{"latex": str, "confidence": float,
"processing_time_ms": int, "provider_version": str}`.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import run_main  # noqa: E402 - must follow sys.path mutation above

# See module docstring: pix2tex exposes no real confidence signal.
_UNMEASURED_CONFIDENCE_PLACEHOLDER = 50.0
_model_cache: dict[str, Any] = {}


def _get_model() -> Any:
    if "model" not in _model_cache:
        from pix2tex.cli import LatexOCR

        _model_cache["model"] = LatexOCR()
    return _model_cache["model"]


def extract(request: dict[str, Any]) -> dict[str, Any]:
    from PIL import Image

    crop_path = request["crop"]
    started = time.perf_counter()
    model = _get_model()
    image = Image.open(crop_path).convert("RGB")
    latex = model(image)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    return {
        "latex": latex,
        "confidence": _UNMEASURED_CONFIDENCE_PLACEHOLDER,
        "processing_time_ms": elapsed_ms,
        "provider_version": _version(),
    }


def _version() -> str:
    try:
        import pix2tex

        return f"pix2tex-{getattr(pix2tex, '__version__', 'unknown')}"
    except Exception:  # noqa: BLE001
        return "pix2tex-unknown"


def health(_request: dict[str, Any]) -> dict[str, Any]:
    import torch

    return {
        "installed": True,
        "version": _version(),
        "gpu_available": bool(torch.cuda.is_available()),
    }


if __name__ == "__main__":
    run_main({"extract": extract, "health": health})
