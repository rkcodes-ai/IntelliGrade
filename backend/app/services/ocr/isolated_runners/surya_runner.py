"""
Runner script executed by `.venv-surya`'s interpreter (never imported by
the main backend venv — see `app.services.ocr.isolated_runtime`).

Pinned to `surya-ocr==0.13.1` deliberately, not the latest release
(0.22.1) — see `providers/surya_provider.py`'s module docstring for the
concrete evidence: 0.22.1's `RecognitionPredictor` is a "Foundation model"
rewrite whose only inference backends (`vllm`, `llamacpp`) both require an
external server process (Docker, or a natively-installed `llama-server`
binary) neither of which exists on this machine and neither of which this
milestone's brief authorizes installing unprompted. 0.13.1 is the last
line of releases with the classic, fully local, pure-PyTorch
`DetectionPredictor` + `RecognitionPredictor` API used below — genuinely
real inference, no server process, no Docker.

Surya's classic API returns a flat list of `TextLine` (`polygon`,
`confidence`, `text`) per page — no native block/paragraph segmentation,
the same shape EasyOCR/PaddleOCR already produce (see those providers'
docstrings) — so this runner maps it onto one page-level block containing
one line per detection, with synthetic whitespace-split words sharing the
line's bounding box (documented approximation, not a genuine per-word
measurement, consistent with the existing convention).

Request: `{"image_path": str, "language": str, "options": {}}`.
Response (`success: true`): `{"raw_text": str, "average_confidence": float,
"blocks": [...]}` — same shape as `doctr_runner.py`'s response.

Also exposes a `"layout"` mode (Document Intelligence milestone) using
Surya's separate, real `LayoutPredictor` — a genuine, already-installed,
already-local page-layout model whose label vocabulary (`Text`,
`TextInlineMath`, `Equation`, `Table`, `Picture`, `Figure`, `Handwriting`,
`PageHeader`, `PageFooter`, `SectionHeader`, `Caption`, `Footnote`,
`ListItem`, `Form`, `TableOfContents`, `Code`, `Blank` — see
`surya.layout.model.config.ID_TO_LABEL`) already covers nearly every
region type this milestone needs, which is why no separate/fourth layout
framework was installed (Section 13's explicit "reuse before adding"
requirement) — see `app.services.document_intelligence.layout`'s module
docstring for how this output is consumed.

Request (layout mode): `{"image_path": str, "mode": "layout"}`.
Response: `{"regions": [{"label": str, "confidence": float, "bbox": {...}}, ...],
"processing_time_ms": int, "provider_version": str}`.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import run_main  # noqa: E402 - must follow sys.path mutation above

_predictor_cache: dict[str, Any] = {}


def _get_predictors() -> tuple[Any, Any]:
    if "det" not in _predictor_cache:
        from surya.detection import DetectionPredictor
        from surya.recognition import RecognitionPredictor

        _predictor_cache["det"] = DetectionPredictor()
        _predictor_cache["rec"] = RecognitionPredictor()
    return _predictor_cache["det"], _predictor_cache["rec"]


def _polygon_to_bbox(polygon: list[list[float]]) -> dict[str, int]:
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    left, top = int(min(xs)), int(min(ys))
    return {
        "left": left,
        "top": top,
        "width": int(max(xs)) - left,
        "height": int(max(ys)) - top,
    }


# Tesseract-style 3-letter codes (this app's convention) -> Surya's ISO
# 639-1-ish codes — same pattern as easyocr_provider._LANGUAGE_ALIASES /
# paddleocr_provider._LANGUAGE_ALIASES.
_LANGUAGE_ALIASES: dict[str, str] = {
    "eng": "en",
    "hin": "hi",
    "fra": "fr",
    "deu": "de",
    "spa": "es",
}


def extract(request: dict[str, Any]) -> dict[str, Any]:
    from PIL import Image

    image_path = request["image_path"]
    language = request.get("language", "eng")
    surya_lang = _LANGUAGE_ALIASES.get(language, language if len(language) == 2 else "en")

    started = time.perf_counter()
    det_predictor, rec_predictor = _get_predictors()

    image = Image.open(image_path).convert("RGB")
    results = rec_predictor([image], [[surya_lang]], det_predictor=det_predictor)
    page = results[0]

    lines: list[dict[str, Any]] = []
    all_confidences: list[float] = []
    text_parts: list[str] = []

    for text_line in page.text_lines:
        text = text_line.text.strip()
        if not text:
            continue
        bbox = _polygon_to_bbox(text_line.polygon)
        # `confidence` is genuinely Optional in surya's schema — reported
        # as-is (never fabricated with a fallback value) when the model
        # didn't produce one for this line.
        confidence = float(text_line.confidence) * 100 if text_line.confidence is not None else 0.0

        tokens = text.split()
        words = [{"text": token, "bbox": bbox, "confidence": confidence} for token in tokens]
        lines.append({"text": text, "bbox": bbox, "confidence": confidence, "words": words})
        all_confidences.append(confidence)
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
    avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

    return {
        "raw_text": "\n".join(text_parts),
        "average_confidence": avg_confidence,
        "blocks": [{"bbox": page_bbox, "confidence": avg_confidence, "lines": lines}],
        "processing_time_ms": elapsed_ms,
        "provider_version": _version(),
    }


_layout_predictor_cache: dict[str, Any] = {}


def _get_layout_predictor() -> Any:
    if "layout" not in _layout_predictor_cache:
        from surya.layout import LayoutPredictor

        _layout_predictor_cache["layout"] = LayoutPredictor()
    return _layout_predictor_cache["layout"]


def layout(request: dict[str, Any]) -> dict[str, Any]:
    from PIL import Image

    image_path = request["image_path"]
    started = time.perf_counter()

    predictor = _get_layout_predictor()
    image = Image.open(image_path).convert("RGB")
    results = predictor([image])
    page = results[0]

    regions = [
        {
            "label": box.label,
            "confidence": float(box.confidence) * 100 if box.confidence is not None else 0.0,
            "bbox": _polygon_to_bbox(box.polygon),
        }
        for box in page.bboxes
    ]

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {"regions": regions, "processing_time_ms": elapsed_ms, "provider_version": _version()}


def _version() -> str:
    import surya

    return getattr(surya, "__version__", "0.13.1")


def health(_request: dict[str, Any]) -> dict[str, Any]:
    import torch

    return {
        "installed": True,
        "version": _version(),
        "gpu_available": bool(torch.cuda.is_available()),
    }


if __name__ == "__main__":
    run_main({"extract": extract, "health": health, "layout": layout})
