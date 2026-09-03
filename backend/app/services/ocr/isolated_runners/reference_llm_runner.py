"""
Runner script executed by `.venv-reference-ai`'s interpreter (never
imported by the main backend venv — see
`app.services.ocr.isolated_runtime`).

Wraps `llama-cpp-python` (MIT licensed — verified against the real
`LICENSE.md` in `abetlen/llama-cpp-python`) running a local, quantized
Qwen2.5-1.5B-Instruct GGUF checkpoint (Apache 2.0, official `Qwen/
Qwen2.5-1.5B-Instruct-GGUF` release — see
`document_intelligence`-adjacent `reference_ai_provider.py`'s module
docstring for the full research/selection rationale). Isolated because
this is a new, sizeable (~1.1GB model + a compiled inference runtime)
dependency this project's main venv should never carry, matching the
established Surya/docTR/TrOCR/pix2tex/LanguageTool/fastText precedent —
even though `llama-cpp-python` ships a universal `py3-none-win_amd64`
wheel requiring no compilation, keeping it isolated avoids any risk to
the stable main environment regardless.

CPU-only by design (`n_gpu_layers=0`) — Section 35/55's hardware-safety
requirement: this reference-building path must never contend with OCR's
GPU-capable providers for the same 6GB VRAM, and structured-extraction
quality at this model size does not meaningfully benefit from GPU
offload on a laptop-class card anyway.

Request: `{"prompt": str, "max_tokens": int, "temperature": float,
"mode": "generate"}`. Deterministic settings (`temperature=0.0` by
default — Section 61) so the same evidence produces stable output.

Response (`success: true`): `{"text": str, "processing_time_ms": int,
"model_version": str, "tokens_generated": int}`.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import run_main  # noqa: E402 - must follow sys.path mutation above

_MODEL_PATH = (
    Path(__file__).resolve().parents[4]
    / ".reference-ai-models"
    / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
)
_model_cache: dict[str, Any] = {}

# Conservative, hardware-safe defaults (Section 35/36): small context
# window (this task is short evidence + short structured output, not a
# long-document task), bounded thread count, CPU-only.
_DEFAULT_CONTEXT_TOKENS = 4096
_DEFAULT_MAX_NEW_TOKENS = 768


def _get_model() -> Any:
    if "model" not in _model_cache:
        from llama_cpp import Llama

        _model_cache["model"] = Llama(
            model_path=str(_MODEL_PATH),
            n_ctx=_DEFAULT_CONTEXT_TOKENS,
            n_gpu_layers=0,  # CPU-only -- never contends with OCR's GPU providers
            n_threads=None,  # let llama.cpp pick a bounded, sane default for this CPU
            verbose=False,
        )
    return _model_cache["model"]


def generate(request: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    prompt = str(request["prompt"])
    max_tokens = int(request.get("max_tokens", _DEFAULT_MAX_NEW_TOKENS))
    temperature = float(request.get("temperature", 0.0))  # deterministic by default (Section 61)

    model = _get_model()
    output = model.create_chat_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=1.0,
    )
    text = output["choices"][0]["message"]["content"]
    tokens_generated = int(output.get("usage", {}).get("completion_tokens", 0))

    return {
        "text": text,
        "processing_time_ms": int((time.perf_counter() - started) * 1000),
        "model_version": "qwen2.5-1.5b-instruct-q4_k_m",
        "tokens_generated": tokens_generated,
    }


def health(_request: dict[str, Any]) -> dict[str, Any]:
    return {
        "installed": _MODEL_PATH.exists(),
        "model_path": str(_MODEL_PATH),
        "gpu_available": False,  # deliberately CPU-only, see module docstring
    }


if __name__ == "__main__":
    run_main({"generate": generate, "health": health})
