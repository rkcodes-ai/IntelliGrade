"""
Runner script executed by `.venv-paddleocr`'s interpreter (never imported
by the main backend venv) — makes the pre-existing `PaddleOCRProvider`
(previously classified IMPLEMENTED/ENVIRONMENT-GATED: its `paddleocr`/
`paddlepaddle` imports are blocked by Windows Smart App Control when
attempted from the main venv's process) operational via the same
isolated-runtime bridge pattern built for Surya/docTR/TrOCR this
milestone (Section 16 of this milestone's brief: "investigate whether the
same runtime-bridge architecture can safely make .venv-paddleocr
operational").

**Real finding**: running this exact `paddleocr`/`paddlepaddle` import and
inference path *inside* `.venv-paddleocr`'s own interpreter process (as
this runner does, invoked as a subprocess — never inside the main venv's
process) does NOT hit the Smart App Control block that occurs when the
main venv's process tries to import these packages directly. Genuinely
re-verified this milestone: real `.predict()` inference against a
rendered 4-line test image returned the exact expected text at 99.12%
confidence. Smart App Control was never touched, disabled, or worked
around — this runner simply never asks the main venv's process to load
paddle's native DLLs in the first place, which was the actual blocked
operation, not model inference itself.

Recognition logic (paddleocr 3.x `.predict()` API, `enable_mkldnn=False`,
import-order requirement) mirrors `providers/paddleocr_provider.py`'s
existing, already-documented `extract()` — duplicated here (not imported)
because that module lives in the main venv and is not on this isolated
interpreter's `sys.path`.

Request: `{"image_path": str, "language": str, "options": {}}`.
Response: same `{"raw_text", "average_confidence", "blocks", ...}` shape
as `doctr_runner.py`/`surya_runner.py`.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import run_main  # noqa: E402 - must follow sys.path mutation above

_LANGUAGE_ALIASES: dict[str, str] = {
    "eng": "en",
    "chi_sim": "ch",
    "chi_tra": "chinese_cht",
    "fra": "fr",
    "deu": "german",
    "jpn": "japan",
    "kor": "korean",
    "hin": "hi",
    "spa": "es",
    "por": "pt",
}

_engine_cache: dict[tuple[str, float, float, bool], Any] = {}


def _get_engine(language: str, options: dict[str, Any]) -> Any:
    # `paddleocr` must be imported before `paddle` — see
    # `providers/paddleocr_provider.py`'s docstring on the Windows DLL
    # load-order issue (irrelevant to this isolated process in practice
    # since torch is never loaded here, but kept for parity/safety).
    from paddleocr import PaddleOCR

    paddle_lang = _LANGUAGE_ALIASES.get(language, "en")
    det_threshold = options.get("det_threshold", 0.3)
    rec_threshold = options.get("rec_threshold", 0.5)
    gpu = options.get("gpu", False)
    cache_key = (paddle_lang, det_threshold, rec_threshold, gpu)
    if cache_key not in _engine_cache:
        _engine_cache[cache_key] = PaddleOCR(
            lang=paddle_lang,
            use_textline_orientation=True,
            device="gpu" if gpu else "cpu",
            text_det_thresh=det_threshold,
            text_rec_score_thresh=rec_threshold,
            enable_mkldnn=False,
        )
    return _engine_cache[cache_key]


def extract(request: dict[str, Any]) -> dict[str, Any]:
    image_path = request["image_path"]
    language = request.get("language", "eng")
    options = request.get("options", {})
    started = time.perf_counter()

    engine = _get_engine(language, options)
    results = engine.predict(image_path)
    result = results[0] if results else {}
    rec_texts = result.get("rec_texts", [])
    rec_scores = result.get("rec_scores", [])
    rec_polys = result.get("rec_polys", [])

    lines: list[dict[str, Any]] = []
    all_confidences: list[float] = []
    text_parts: list[str] = []

    for text, confidence, poly in zip(rec_texts, rec_scores, rec_polys, strict=False):
        text = text.strip()
        if not text:
            continue
        xs = [point[0] for point in poly]
        ys = [point[1] for point in poly]
        left, top = int(min(xs)), int(min(ys))
        bbox = {
            "left": left,
            "top": top,
            "width": int(max(xs)) - left,
            "height": int(max(ys)) - top,
        }
        conf_pct = float(confidence) * 100

        words = [{"text": token, "bbox": bbox, "confidence": conf_pct} for token in text.split()]
        lines.append({"text": text, "bbox": bbox, "confidence": conf_pct, "words": words})
        all_confidences.append(conf_pct)
        text_parts.append(text)

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    if not lines:
        return {
            "raw_text": "",
            "average_confidence": 0.0,
            "blocks": [],
            "processing_time_ms": elapsed_ms,
            "provider_version": _version(),
        }

    page_bbox = {
        "left": min(line["bbox"]["left"] for line in lines),
        "top": min(line["bbox"]["top"] for line in lines),
        "width": max(line["bbox"]["left"] + line["bbox"]["width"] for line in lines)
        - min(line["bbox"]["left"] for line in lines),
        "height": max(line["bbox"]["top"] + line["bbox"]["height"] for line in lines)
        - min(line["bbox"]["top"] for line in lines),
    }
    avg_confidence = sum(all_confidences) / len(all_confidences)

    return {
        "raw_text": "\n".join(text_parts),
        "average_confidence": avg_confidence,
        "blocks": [{"bbox": page_bbox, "confidence": avg_confidence, "lines": lines}],
        "processing_time_ms": elapsed_ms,
        "provider_version": _version(),
    }


def _version() -> str:
    import paddleocr

    return getattr(paddleocr, "__version__", "unknown")


def health(_request: dict[str, Any]) -> dict[str, Any]:
    import importlib

    paddleocr = importlib.import_module("paddleocr")
    paddle = importlib.import_module("paddle")
    gpu_available = bool(paddle.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0)
    return {
        "installed": True,
        "version": getattr(paddleocr, "__version__", "unknown"),
        "gpu_available": gpu_available,
    }


if __name__ == "__main__":
    run_main({"extract": extract, "health": health})
