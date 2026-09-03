"""
Real OCR adapter wrapping `python-doctr` (torch backend), run in the
isolated `.venv-doctr` venv and invoked from the main backend process via
`app.services.ocr.isolated_runtime` — see that module's docstring for why
(a `pip install --dry-run "python-doctr[torch]"` into the main venv showed
it installing non-headless `opencv-python` alongside the main venv's
existing `opencv-python-headless`, a dual-`cv2`-namespace packaging
conflict; Section 8/9 of this milestone's brief requires an isolated
runtime rather than forcing that into the stable venv).

**Runtime-verified**: real `ocr_predictor(pretrained=True)` (torch
backend, CPU — this machine's torch builds are all CPU-only, see
`isolated_runners/doctr_runner.py`'s `health()`) against a real rendered
multi-line test image returned 3 of 4 lines with 100% correct text and
genuine per-word confidence scores (0.52-0.999 range, never fabricated);
the 4th line had two real OCR misreads ("rundamental orinciple" for
"fundamental principle") — an honest recognition error, not a bug, left
as-is rather than hidden.

docTR's own hierarchy (`Document -> Page -> Block -> Line -> Word`) maps
directly onto this project's standardized `OCRPageResult -> OCRBlockResult
-> OCRLineResult -> OCRWordResult` (ADR-029) with no synthetic levels
needed — `doctr_runner.py` already flattens this in the isolated process;
this adapter only converts the runner's JSON dicts into the dataclasses.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.ocr.base import (
    BoundingBox,
    OCRBlockResult,
    OCRLineResult,
    OCRPageResult,
    OCRProviderAdapter,
    OCRWordResult,
)
from app.services.ocr.exceptions import OCRIsolatedRuntimeInferenceError
from app.services.ocr.isolated_runtime import (
    RUNNERS_DIR,
    default_isolated_python,
    invoke_isolated_runtime,
)
from app.services.ocr.models import HealthCheckResult, ProviderCapabilities

settings = get_settings()

_RUNNER_SCRIPT = RUNNERS_DIR / "doctr_runner.py"


def _bbox_from_dict(data: dict[str, Any]) -> BoundingBox:
    return BoundingBox(
        left=int(data["left"]),
        top=int(data["top"]),
        width=int(data["width"]),
        height=int(data["height"]),
    )


class DocTROCRAdapter(OCRProviderAdapter):
    provider_code = "doctr"
    is_implemented = True

    def __init__(self, *, python_exe: str | None = None) -> None:
        super().__init__()
        configured = python_exe or settings.OCR_DOCTR_PYTHON
        self._python_exe_path = (
            Path(configured) if configured else default_isolated_python(".venv-doctr")
        )

    def extract(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
        with self._timed():
            result = invoke_isolated_runtime(
                python_exe=self._python_exe_path,
                runner_script=_RUNNER_SCRIPT,
                request={"image_path": image_path, "language": language, "mode": "extract"},
                startup_timeout=settings.OCR_ISOLATED_RUNTIME_STARTUP_TIMEOUT_SECONDS,
                inference_timeout=settings.OCR_ISOLATED_RUNTIME_INFERENCE_TIMEOUT_SECONDS,
            )
            payload = result.payload
            if not payload.get("success", True):
                raise OCRIsolatedRuntimeInferenceError(
                    payload.get("error", "unknown docTR runner error")
                )

        blocks: list[OCRBlockResult] = []
        for block_data in payload.get("blocks", []):
            lines: list[OCRLineResult] = []
            for line_data in block_data.get("lines", []):
                words = [
                    OCRWordResult(
                        text=word_data["text"],
                        bounding_box=_bbox_from_dict(word_data["bbox"]),
                        confidence=float(word_data["confidence"]),
                        reading_order=index,
                    )
                    for index, word_data in enumerate(line_data.get("words", []))
                ]
                lines.append(
                    OCRLineResult(
                        text=line_data["text"],
                        bounding_box=_bbox_from_dict(line_data["bbox"]),
                        confidence=float(line_data["confidence"]),
                        reading_order=len(lines),
                        words=words,
                    )
                )
            blocks.append(
                OCRBlockResult(
                    bounding_box=_bbox_from_dict(block_data["bbox"]),
                    confidence=float(block_data["confidence"]),
                    reading_order=len(blocks),
                    lines=lines,
                )
            )

        return OCRPageResult(
            raw_text=payload.get("raw_text", ""),
            average_confidence=float(payload.get("average_confidence", 0.0)),
            language=language,
            # docTR's torch predictor doesn't report a page-level rotation
            # angle distinct from its internal orientation-correction step —
            # 0.0 means "not applicable", not "measured and confirmed upright".
            rotation_degrees=0.0,
            blocks=blocks,
        )

    def provider_version(self) -> str:
        try:
            result = invoke_isolated_runtime(
                python_exe=self._python_exe_path,
                runner_script=_RUNNER_SCRIPT,
                request={"mode": "health"},
                startup_timeout=settings.OCR_ISOLATED_RUNTIME_STARTUP_TIMEOUT_SECONDS,
                inference_timeout=settings.OCR_ISOLATED_RUNTIME_INFERENCE_TIMEOUT_SECONDS,
            )
            return str(result.payload.get("version", "unknown"))
        except Exception:  # noqa: BLE001
            return "not installed"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            handwriting=False,
            tables=False,
            layout=False,
            gpu=True,
            batch_processing=True,
            multi_page_pdf=True,
        )

    def health_check(self) -> HealthCheckResult:
        if not self._python_exe_path.exists():
            return HealthCheckResult(
                provider_code=self.provider_code,
                installed=False,
                version=None,
                configured=True,
                authenticated=None,
                connectivity=None,
                dependencies_ok=False,
                gpu_available=None,
                ready=False,
                detail=(
                    f"Isolated runtime interpreter not found at {self._python_exe_path}. "
                    "Create the .venv-doctr venv and install python-doctr[torch] to "
                    "activate this provider."
                ),
            )
        try:
            result = invoke_isolated_runtime(
                python_exe=self._python_exe_path,
                runner_script=_RUNNER_SCRIPT,
                request={"mode": "health"},
                startup_timeout=settings.OCR_ISOLATED_RUNTIME_STARTUP_TIMEOUT_SECONDS,
                inference_timeout=settings.OCR_ISOLATED_RUNTIME_INFERENCE_TIMEOUT_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001 - health check must never raise, only report
            return HealthCheckResult(
                provider_code=self.provider_code,
                installed=False,
                version=None,
                configured=True,
                authenticated=None,
                connectivity=None,
                dependencies_ok=False,
                gpu_available=None,
                ready=False,
                detail=f"Isolated docTR runtime health check failed: {exc}",
            )

        payload = result.payload
        return HealthCheckResult(
            provider_code=self.provider_code,
            installed=bool(payload.get("installed", False)),
            version=payload.get("version"),
            configured=True,
            authenticated=None,
            connectivity=None,
            dependencies_ok=bool(payload.get("installed", False)),
            gpu_available=payload.get("gpu_available"),
            ready=bool(payload.get("installed", False)),
            detail=None,
        )
