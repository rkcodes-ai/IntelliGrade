"""
Real OCR adapter wrapping Microsoft TrOCR (`microsoft/trocr-base-handwritten`,
via `transformers`/`torch`), run in the isolated `.venv-trocr` venv and
invoked from the main backend process via `app.services.ocr.isolated_runtime`
(kept isolated for the same reason as Surya/docTR — see those providers'
docstrings — even though TrOCR's own dependency tree turned out not to
conflict with the main venv, consistency of "heavy ML provider -> isolated
runtime" was preferred over a one-off exception).

TrOCR is a **line-level handwriting recognizer, not a page-level OCR
engine** (Section 11/13 of this milestone's brief is explicit that it must
never be used as whole-page-to-TrOCR). This adapter therefore implements
the required detection -> crop -> recognize -> reconstruct pipeline:

1. **Line detection**: reuses the already-verified, already-in-process
   `EasyOCRProvider` purely as a line detector — `EasyOCRProvider.extract()`
   is called and only its line-level `bounding_box`es are kept; its own
   recognized text is discarded (TrOCR re-recognizes each region itself).
   This is a deliberate reuse of an existing operational detector rather
   than introducing a second detection framework (Section 11's explicit
   instruction).
2. **Crop**: each detected line's region (plus a small padding margin, to
   avoid clipping ascenders/descenders) is cropped from the original page
   image into its own temporary PNG.
3. **Recognize**: all crops are sent to the isolated `.venv-trocr` runner
   in one subprocess call (`isolated_runners/trocr_runner.py`), which runs
   real `VisionEncoderDecoderModel.generate()` per crop.
4. **Reconstruct**: recognized text is reattached to each line's original
   detected bounding box, in the detector's own reading order — no
   re-ordering heuristic invented here.

TrOCR's own `generate()` has no native calibrated confidence; the runner
computes a genuine per-token softmax-probability proxy instead of
fabricating one (see the runner's docstring) — surfaced here unchanged,
never re-scaled to look like a different kind of number.

`transformers` is pinned to `4.46.3` in `.venv-trocr` — the newer
`5.14.1` (installed by a plain `pip install transformers` at the time of
this milestone) failed to load `TrOCRProcessor.from_pretrained(...)`'s
tokenizer with `ValueError: Couldn't instantiate the backend tokenizer
...need to have sentencepiece or tiktoken installed` even with
`sentencepiece` genuinely installed — a real, reproducible incompatibility
between that bleeding-edge `transformers` release and this checkpoint's
tokenizer files, not a guess. `4.46.3` loads and runs it correctly
(confirmed by real inference — see this milestone's final report).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

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
from app.services.ocr.providers.easyocr_provider import EasyOCRProvider

settings = get_settings()

_RUNNER_SCRIPT = RUNNERS_DIR / "trocr_runner.py"
_CROP_PADDING_PX = 4


def _union_box(boxes: list[BoundingBox]) -> BoundingBox:
    left = min(b.left for b in boxes)
    top = min(b.top for b in boxes)
    right = max(b.left + b.width for b in boxes)
    bottom = max(b.top + b.height for b in boxes)
    return BoundingBox(left=left, top=top, width=right - left, height=bottom - top)


class TrOCRHandwrittenAdapter(OCRProviderAdapter):
    provider_code = "trocr_handwritten"
    is_implemented = True

    def __init__(
        self,
        *,
        python_exe: str | None = None,
        line_detector: OCRProviderAdapter | None = None,
    ) -> None:
        super().__init__()
        configured = python_exe or settings.OCR_TROCR_PYTHON
        self._python_exe_path = (
            Path(configured) if configured else default_isolated_python(".venv-trocr")
        )
        self._line_detector = line_detector or EasyOCRProvider()

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
                result.get("error", "unknown TrOCR runner error")
            )
        return result

    def extract(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
        # Step 1: detect line regions using the existing, already-verified
        # EasyOCR adapter — its recognized text is discarded, only geometry
        # is kept (see module docstring).
        detector_result = self._line_detector.extract(image_path, language=language)
        detected_lines = [line for block in detector_result.blocks for line in block.lines]

        if not detected_lines:
            return OCRPageResult(
                raw_text="",
                average_confidence=0.0,
                language=language,
                rotation_degrees=0.0,
                blocks=[],
            )

        with self._timed(), tempfile.TemporaryDirectory(prefix="trocr-crops-") as crop_dir:
            image = Image.open(image_path).convert("RGB")
            crop_paths: list[str] = []
            for index, detected_line in enumerate(detected_lines):
                box = detected_line.bounding_box
                left = max(box.left - _CROP_PADDING_PX, 0)
                top = max(box.top - _CROP_PADDING_PX, 0)
                right = min(box.left + box.width + _CROP_PADDING_PX, image.width)
                bottom = min(box.top + box.height + _CROP_PADDING_PX, image.height)
                crop = image.crop((left, top, right, bottom))
                crop_path = str(Path(crop_dir) / f"line_{index}.png")
                crop.save(crop_path)
                crop_paths.append(crop_path)

            payload = self._invoke({"crops": crop_paths, "mode": "extract"})

        recognized = payload.get("results", [])
        lines: list[OCRLineResult] = []
        all_confidences: list[float] = []
        text_parts: list[str] = []

        for detected_line, recognition in zip(detected_lines, recognized, strict=True):
            text = recognition["text"].strip()
            confidence = float(recognition["confidence"])
            if not text:
                continue
            # Synthetic per-word boxes sharing the line's box — same documented
            # approximation as EasyOCRProvider/SuryaOCRAdapter (no per-word geometry available).
            words = [
                OCRWordResult(
                    text=token,
                    bounding_box=detected_line.bounding_box,
                    confidence=confidence,
                    reading_order=token_index,
                )
                for token_index, token in enumerate(text.split())
            ]
            lines.append(
                OCRLineResult(
                    text=text,
                    bounding_box=detected_line.bounding_box,
                    confidence=confidence,
                    reading_order=len(lines),
                    words=words,
                )
            )
            all_confidences.append(confidence)
            text_parts.append(text)

        if not lines:
            return OCRPageResult(
                raw_text="",
                average_confidence=0.0,
                language=language,
                rotation_degrees=0.0,
                blocks=[],
            )

        avg_confidence = sum(all_confidences) / len(all_confidences)
        page_block = OCRBlockResult(
            bounding_box=_union_box([line.bounding_box for line in lines]),
            confidence=avg_confidence,
            reading_order=0,
            lines=lines,
        )
        return OCRPageResult(
            raw_text="\n".join(text_parts),
            average_confidence=avg_confidence,
            language=language,
            rotation_degrees=0.0,
            blocks=[page_block],
        )

    def extract_handwriting(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
        """TrOCR's checkpoint IS a handwriting specialist — `extract()`
        already is the handwriting path, unlike providers where this
        method is a best-effort fallback."""
        return self.extract(image_path, language=language)

    def provider_version(self) -> str:
        try:
            return str(self._invoke({"mode": "health"}).get("version", "unknown"))
        except Exception:  # noqa: BLE001
            return "not installed"

    def supported_languages(self) -> list[str]:
        # `microsoft/trocr-base-handwritten` is an English-only checkpoint —
        # not a guessed list, this is the model card's documented scope.
        return ["eng"]

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            handwriting=True,
            tables=False,
            layout=False,
            gpu=True,
            batch_processing=False,
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
                    "Create the .venv-trocr venv and install transformers==4.46.3 + torch to "
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
                detail=f"Isolated TrOCR runtime health check failed: {exc}",
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
