"""
Runner script executed by `.venv-trocr`'s interpreter (never imported by
the main backend venv — see `app.services.ocr.isolated_runtime`).

TrOCR (`microsoft/trocr-base-handwritten`) is a line-level recognizer, not
a page-level OCR engine — it expects one already-cropped, roughly
single-line image per call (see `providers/trocr_provider.py`'s module
docstring for the full line-detection/cropping pipeline this runner
plugs into). This runner therefore takes a **list of already-cropped line
image paths** (produced by the main-venv adapter, which reuses the
existing, already-verified EasyOCR adapter purely as a line detector — no
new detection framework) and returns one recognized text + confidence per
crop, in the same order.

TrOCR's `generate()` doesn't expose a native calibrated confidence score.
Rather than fabricate one, this runner computes a genuine (labelled as
such) proxy from the model's own per-token output distribution: the mean
of `softmax(logits).max()` across generated tokens, converted to a 0-100
scale. This is a real, reproducible measurement of the model's own
token-level certainty — not a guessed or hardcoded number — but it is
explicitly a computed proxy, not a metric TrOCR itself reports, and is
documented as such everywhere it's surfaced.

Request: `{"crops": [str, ...], "options": {}}` (no `language` — TrOCR's
handwritten checkpoint is English-only).
Response (`success: true`): `{"results": [{"text": str, "confidence":
float}, ...], "processing_time_ms": int, "provider_version": str}`.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import run_main  # noqa: E402 - must follow sys.path mutation above

_MODEL_NAME = "microsoft/trocr-base-handwritten"
_model_cache: dict[str, Any] = {}


def _get_model() -> tuple[Any, Any]:
    if "model" not in _model_cache:
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        _model_cache["processor"] = TrOCRProcessor.from_pretrained(_MODEL_NAME)
        _model_cache["model"] = VisionEncoderDecoderModel.from_pretrained(_MODEL_NAME)
    return _model_cache["processor"], _model_cache["model"]


def _recognize_one(processor: Any, model: Any, crop_path: str) -> dict[str, Any]:
    import torch
    from PIL import Image

    image = Image.open(crop_path).convert("RGB")
    pixel_values = processor(images=image, return_tensors="pt").pixel_values
    with torch.no_grad():
        output = model.generate(
            pixel_values,
            num_beams=1,  # greedy — keeps the per-token softmax confidence proxy meaningful
            max_new_tokens=64,
            output_scores=True,
            return_dict_in_generate=True,
        )

    text = processor.batch_decode(output.sequences, skip_special_tokens=True)[0].strip()

    # See module docstring: a genuine but explicitly-labelled proxy, not a
    # native TrOCR confidence.
    token_confidences: list[float] = []
    for step_logits in output.scores:
        probs = torch.softmax(step_logits[0], dim=-1)
        token_confidences.append(float(probs.max().item()))
    confidence = (
        (sum(token_confidences) / len(token_confidences) * 100) if token_confidences else 0.0
    )

    return {"text": text, "confidence": confidence}


def extract(request: dict[str, Any]) -> dict[str, Any]:
    crops: list[str] = request["crops"]
    started = time.perf_counter()
    processor, model = _get_model()

    results = [_recognize_one(processor, model, crop_path) for crop_path in crops]

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {"results": results, "processing_time_ms": elapsed_ms, "provider_version": _version()}


def _version() -> str:
    import transformers

    return f"transformers-{getattr(transformers, '__version__', 'unknown')}/{_MODEL_NAME}"


def health(_request: dict[str, Any]) -> dict[str, Any]:
    import torch

    return {
        "installed": True,
        "version": _version(),
        "gpu_available": bool(torch.cuda.is_available()),
    }


if __name__ == "__main__":
    run_main({"extract": extract, "health": health})
