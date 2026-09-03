"""
Real OCR adapter wrapping `surya-ocr`, run in the isolated `.venv-surya`
venv and invoked from the main backend process via
`app.services.ocr.isolated_runtime` (a `pip install --dry-run surya-ocr`
into the main venv showed it would downgrade `pillow` 12.3.0->10.4.0 and
`opencv-python-headless` 5.0.0.93->4.11.0.86 — a direct Section 8
violation if forced into the stable venv).

**Version pinned to `surya-ocr==0.13.1`, not the latest 0.22.1** — a real,
concrete environment finding, not a preference: 0.22.1's default
`RecognitionPredictor` (the "Foundation model" rewrite) has exactly two
inference backends, both requiring an external server process this
machine doesn't have and this milestone doesn't authorize installing
unprompted:

- `vllm` backend: spawns a Docker container (`SpawnError: docker binary
  not found` — confirmed by real attempted inference, not assumption).
- `llamacpp` backend: spawns a native `llama-server` binary via
  `shutil.which()`, with install instructions documented only for
  macOS/Linux (`brew install llama.cpp`) — no Windows path offered by the
  library itself, and downloading/running an unsigned third-party binary
  from GitHub Releases to stand up a local model server is a real
  infrastructure change this milestone's brief doesn't ask for.

`surya-ocr==0.13.1` is the last release line with the classic, fully
local, pure-PyTorch `DetectionPredictor`/`RecognitionPredictor` API (no
server process) — genuinely real inference, confirmed end-to-end against
a rendered multi-line test image (see `isolated_runners/surya_runner.py`'s
docstring and this milestone's final report for the actual numbers).

Surya's classic API returns a flat list of text lines (no native block
segmentation) — mapped onto one page-level block, same documented
approximation already used by `EasyOCRProvider`/`PaddleOCRProvider` for
the same reason (see their docstrings).
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

_RUNNER_SCRIPT = RUNNERS_DIR / "surya_runner.py"


def _bbox_from_dict(data: dict[str, Any]) -> BoundingBox:
    return BoundingBox(
        left=int(data["left"]),
        top=int(data["top"]),
        width=int(data["width"]),
        height=int(data["height"]),
    )


class SuryaOCRAdapter(OCRProviderAdapter):
    provider_code = "surya"
    is_implemented = True

    def __init__(self, *, python_exe: str | None = None) -> None:
        super().__init__()
        configured = python_exe or settings.OCR_SURYA_PYTHON
        self._python_exe_path = (
            Path(configured) if configured else default_isolated_python(".venv-surya")
        )

    def _invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        result = invoke_isolated_runtime(
            python_exe=self._python_exe_path,
            runner_script=_RUNNER_SCRIPT,
            request=request,
            startup_timeout=settings.OCR_ISOLATED_RUNTIME_STARTUP_TIMEOUT_SECONDS,
            inference_timeout=settings.OCR_ISOLATED_RUNTIME_INFERENCE_TIMEOUT_SECONDS,
        ).payload
        if not result.get("success", True):
            raise OCRIsolatedRuntimeInferenceError(
                result.get("error", "unknown Surya runner error")
            )
        return result

    def extract(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
        with self._timed():
            payload = self._invoke(
                {"image_path": image_path, "language": language, "mode": "extract"}
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
            # Surya's detector corrects line-level skew internally rather
            # than reporting one page-level rotation value — 0.0 means "not
            # applicable", not "measured and confirmed upright".
            rotation_degrees=0.0,
            blocks=blocks,
        )

    def provider_version(self) -> str:
        try:
            return str(self._invoke({"mode": "health"}).get("version", "unknown"))
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
                    "Create the .venv-surya venv and install surya-ocr==0.13.1 to "
                    "activate this provider."
                ),
            )
        try:
            payload = self._invoke({"mode": "health"})
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
                detail=f"Isolated Surya runtime health check failed: {exc}",
            )

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
