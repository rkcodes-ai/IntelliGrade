"""
Runner script executed by `.venv-langid`'s interpreter (never imported
by the main backend venv — see `app.services.ocr.isolated_runtime`).

Wraps fastText's official `lid.176` language-identification model
(`fasttext-wheel`, MIT-licensed software; the `lid.176.ftz` model itself
is CC-BY-SA-3.0 — see `document_intelligence/language_detection.py`'s
module docstring for the full license note). Isolated because
`fasttext-wheel` has no prebuilt Windows wheel for Python 3.13 (this
project's main-venv/other-isolated-venv version) — only up to cp312 —
so `.venv-langid` is deliberately Python 3.12, avoiding a from-source
compile on Windows entirely (a real, confirmed constraint, not a
theoretical one).

Also pins `numpy<2` in this venv specifically: `fasttext-wheel==0.9.2`'s
own `FastText.py` calls `np.array(probs, copy=False)`, which raises
`ValueError: Unable to avoid copy...` under NumPy>=2's stricter
`copy=False` semantics — a real, reproduced incompatibility (confirmed
via direct invocation during this milestone), fixed the same way
`transformers==4.46.3` was pinned for TrOCR: pin the dependency that's
actually broken, don't patch third-party library internals.

Request: `{"text": str, "top_k": int, "mode": "predict"}`.
Response (`success: true`): `{"predictions": [{"language": str,
"confidence": float}, ...], "processing_time_ms": int,
"model_version": str}`.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import run_main  # noqa: E402 - must follow sys.path mutation above

_MODEL_PATH = Path(__file__).resolve().parents[4] / ".langid-models" / "lid.176.ftz"
_model_cache: dict[str, Any] = {}


def _get_model() -> Any:
    if "model" not in _model_cache:
        import fasttext

        _model_cache["model"] = fasttext.load_model(str(_MODEL_PATH))
    return _model_cache["model"]


def predict(request: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    text = str(request["text"]).replace("\n", " ").strip()
    top_k = int(request.get("top_k", 3))

    if not text:
        return {
            "predictions": [],
            "processing_time_ms": int((time.perf_counter() - started) * 1000),
            "model_version": "lid.176.ftz",
        }

    model = _get_model()
    labels, probabilities = model.predict(text, k=top_k)
    predictions = [
        {"language": label.replace("__label__", ""), "confidence": float(prob)}
        for label, prob in zip(labels, probabilities, strict=True)
    ]
    return {
        "predictions": predictions,
        "processing_time_ms": int((time.perf_counter() - started) * 1000),
        "model_version": "lid.176.ftz",
    }


def health(_request: dict[str, Any]) -> dict[str, Any]:
    installed = _MODEL_PATH.exists()
    return {"installed": installed, "model_path": str(_MODEL_PATH), "gpu_available": False}


if __name__ == "__main__":
    run_main({"predict": predict, "health": health})
