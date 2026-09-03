"""
Runner script executed by `.venv-doctr`'s interpreter (never imported by the
main backend venv — see `app.services.ocr.isolated_runtime`).

Uses python-doctr's stable public API (`doctr.io.DocumentFile` +
`doctr.models.ocr_predictor`), unchanged across doctr releases for years:
`ocr_predictor(pretrained=True)` returns a callable that takes a list of
page arrays and returns a `Document` with `.pages[i].blocks[j].lines[k].words[l]`,
each word exposing `.value` (text), `.confidence` (0-1), and `.geometry`
(`((xmin, ymin), (xmax, ymax))` as *relative* [0, 1] coordinates — converted
to pixel `BoundingBox`-shaped dicts here using `page.dimensions`).

Request: `{"image_path": str, "language": str, "options": {}}`.
Response (`success: true`): `{"raw_text": str, "average_confidence": float,
"blocks": [{"bbox": {...}, "confidence": float, "lines": [{"text": str,
"bbox": {...}, "confidence": float, "words": [{"text": str, "bbox": {...},
"confidence": float}]}]}], "processing_time_ms": int, "provider_version": str}`.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import run_main  # noqa: E402 - must follow sys.path mutation above

_model_cache: dict[str, Any] = {}


def _get_model() -> Any:
    if "model" not in _model_cache:
        from doctr.models import ocr_predictor

        _model_cache["model"] = ocr_predictor(pretrained=True)
    return _model_cache["model"]


def _rel_to_bbox(
    geometry: tuple[tuple[float, float], tuple[float, float]], width: int, height: int
) -> dict[str, int]:
    (xmin, ymin), (xmax, ymax) = geometry
    left, top = int(xmin * width), int(ymin * height)
    return {
        "left": left,
        "top": top,
        "width": max(int(xmax * width) - left, 0),
        "height": max(int(ymax * height) - top, 0),
    }


def extract(request: dict[str, Any]) -> dict[str, Any]:
    from doctr.io import DocumentFile

    image_path = request["image_path"]
    started = time.perf_counter()

    model = _get_model()
    doc = DocumentFile.from_images(image_path)
    result = model(doc)
    page = result.pages[0]
    height, width = page.dimensions  # doctr reports (height, width)

    out_blocks: list[dict[str, Any]] = []
    all_confidences: list[float] = []
    text_lines: list[str] = []

    for block in page.blocks:
        out_lines: list[dict[str, Any]] = []
        block_confidences: list[float] = []
        for line in block.lines:
            out_words: list[dict[str, Any]] = []
            word_confidences: list[float] = []
            for word in line.words:
                conf_pct = float(word.confidence) * 100
                out_words.append(
                    {
                        "text": word.value,
                        "bbox": _rel_to_bbox(word.geometry, width, height),
                        "confidence": conf_pct,
                    }
                )
                word_confidences.append(conf_pct)

            line_text = " ".join(w["text"] for w in out_words)
            line_conf = sum(word_confidences) / len(word_confidences) if word_confidences else 0.0
            out_lines.append(
                {
                    "text": line_text,
                    "bbox": _rel_to_bbox(line.geometry, width, height),
                    "confidence": line_conf,
                    "words": out_words,
                }
            )
            block_confidences.extend(word_confidences)
            if line_text:
                text_lines.append(line_text)

        block_conf = sum(block_confidences) / len(block_confidences) if block_confidences else 0.0
        out_blocks.append(
            {
                "bbox": _rel_to_bbox(block.geometry, width, height),
                "confidence": block_conf,
                "lines": out_lines,
            }
        )
        all_confidences.extend(block_confidences)

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    import doctr

    avg_confidence = (sum(all_confidences) / len(all_confidences)) if all_confidences else 0.0
    return {
        "raw_text": "\n".join(text_lines),
        "average_confidence": avg_confidence,
        "blocks": out_blocks,
        "processing_time_ms": elapsed_ms,
        "provider_version": getattr(doctr, "__version__", "unknown"),
    }


def health(_request: dict[str, Any]) -> dict[str, Any]:
    import doctr
    import torch

    return {
        "installed": True,
        "version": getattr(doctr, "__version__", "unknown"),
        "gpu_available": bool(torch.cuda.is_available()),
    }


if __name__ == "__main__":
    run_main({"extract": extract, "health": health})
