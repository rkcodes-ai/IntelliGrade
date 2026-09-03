"""
Real OCR adapter wrapping `easyocr` (PyTorch-backed, CPU or GPU).

EasyOCR's `Reader.readtext()` returns flat text-region detections (each a
4-point quadrilateral + text + confidence) — it has no native block/
paragraph segmentation the way Tesseract's TSV output does. To honor the
standardized Block -> Line -> Word hierarchy without fabricating structure
EasyOCR doesn't provide:
  - every detected region becomes one `OCRLineResult`
  - all lines on a page are wrapped in a single page-level `OCRBlockResult`
    (EasyOCR doesn't segment blocks/columns)
  - each line's text is split on whitespace into synthetic `OCRWordResult`s
    that all share the *line's* bounding box (EasyOCR doesn't return
    per-word boxes) — this is a documented approximation, not a real
    per-word measurement.

`Reader` construction loads (and on first run, downloads) detector/
recognizer models — genuinely expensive, so it happens once in
`initialize()` and is cached on the instance, not per `extract()` call.
"""

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
from app.services.ocr.exceptions import OCRDependencyMissingError
from app.services.ocr.models import HealthCheckResult, ProviderCapabilities

settings = get_settings()

# Tesseract-style 3-letter codes (this app's existing convention, e.g. the
# Celery task's hardcoded `_DEFAULT_LANGUAGE = "eng"`) mapped to EasyOCR's
# ISO 639-1 codes — EasyOCR ships its own supported-language list; this is
# only a convenience alias for the handful of languages IntelliGrade's
# upload pipeline is documented to expect. Anything unmapped falls back to
# English rather than raising, since guessing "en" for an unknown code is
# safer than crashing an otherwise-successful upload.
_LANGUAGE_ALIASES: dict[str, str] = {
    "eng": "en",
    "hin": "hi",
    "fra": "fr",
    "deu": "de",
    "spa": "es",
    "por": "pt",
    "ara": "ar",
    "chi_sim": "ch_sim",
    "chi_tra": "ch_tra",
    "jpn": "ja",
    "kor": "ko",
    "tam": "ta",
    "tel": "te",
}


def _to_easyocr_language(code: str) -> str:
    if len(code) == 2:  # already an EasyOCR-style code
        return code
    return _LANGUAGE_ALIASES.get(code, "en")


class EasyOCRProvider(OCRProviderAdapter):
    provider_code = "easyocr"
    is_implemented = True

    def __init__(self, *, gpu: bool | None = None, model_dir: str | None = None) -> None:
        super().__init__()
        self.gpu = settings.OCR_EASYOCR_GPU if gpu is None else gpu
        self.model_dir = model_dir or settings.OCR_EASYOCR_MODEL_DIR
        self._reader: Any | None = None
        self._reader_languages: list[str] | None = None

    def _get_reader(self, language: str) -> Any:
        try:
            import easyocr  # deferred: only pay the heavy import cost if this provider is used
        except Exception as exc:
            # Deliberately broad: a missing package raises ImportError, but a
            # present-but-blocked native dependency (e.g. torch's compiled
            # DLLs refused by a Windows Application Control / code-integrity
            # policy) raises OSError instead — both mean "this provider
            # cannot run here right now", and both must surface as a clean
            # `OCRDependencyMissingError`, never an uncaught crash.
            raise OCRDependencyMissingError(
                "The 'easyocr' package (and its 'torch' dependency) could not be loaded in this "
                f"environment ({exc}). Install/enable it to activate this provider, or select a "
                "different one."
            ) from exc

        easyocr_lang = _to_easyocr_language(language)
        languages = sorted(
            {easyocr_lang, "en"}
        )  # EasyOCR always wants "en" bundled per its own docs
        if self._reader is not None and self._reader_languages == languages:
            return self._reader

        self._reader = easyocr.Reader(
            languages,
            gpu=self.gpu,
            model_storage_directory=self.model_dir,
            download_enabled=True,
            verbose=False,
        )
        self._reader_languages = languages
        return self._reader

    def initialize(self) -> None:
        """Warms the model cache for English up front so the first real
        `extract()` call isn't the one paying for model load/download."""
        self._get_reader("eng")

    def shutdown(self) -> None:
        self._reader = None
        self._reader_languages = None

    def extract(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
        with self._timed():
            reader = self._get_reader(language)
            detections = reader.readtext(image_path, detail=1)

            lines: list[OCRLineResult] = []
            all_confidences: list[float] = []
            text_parts: list[str] = []
            reading_order = 0

            for quad, text, confidence in detections:
                text = text.strip()
                if not text:
                    continue
                xs = [point[0] for point in quad]
                ys = [point[1] for point in quad]
                left, top = int(min(xs)), int(min(ys))
                width, height = int(max(xs) - min(xs)), int(max(ys) - min(ys))
                bbox = BoundingBox(left=left, top=top, width=width, height=height)
                conf_pct = float(confidence) * 100

                words = [
                    OCRWordResult(
                        text=token,
                        bounding_box=bbox,  # approximation — see module docstring
                        confidence=conf_pct,
                        reading_order=reading_order + token_index,
                    )
                    for token_index, token in enumerate(text.split())
                ]
                reading_order += len(words)

                lines.append(
                    OCRLineResult(
                        text=text,
                        bounding_box=bbox,
                        confidence=conf_pct,
                        reading_order=len(lines),
                        words=words,
                    )
                )
                all_confidences.append(conf_pct)
                text_parts.append(text)

        if not lines:
            return OCRPageResult(
                raw_text="",
                average_confidence=0.0,
                language=language,
                rotation_degrees=0.0,
                blocks=[],
            )

        page_block = OCRBlockResult(
            bounding_box=_union_box([line.bounding_box for line in lines]),
            confidence=sum(all_confidences) / len(all_confidences),
            reading_order=0,
            lines=lines,
        )

        return OCRPageResult(
            raw_text="\n".join(text_parts),
            average_confidence=sum(all_confidences) / len(all_confidences),
            language=language,
            # EasyOCR has no orientation-detection step of its own — 0.0 is
            # "not measured", not a claim the page is actually unrotated.
            rotation_degrees=0.0,
            blocks=[page_block],
        )

    def extract_handwriting(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
        """EasyOCR's default recognizer already handles a meaningful range
        of handwritten text (a documented capability, unlike Tesseract's
        print-only LSTM models) — same call path as `extract()`, no
        separate handwriting-specific model in this SDK."""
        return self.extract(image_path, language=language)

    def provider_version(self) -> str:
        try:
            import easyocr

            return getattr(easyocr, "__version__", "unknown")
        except Exception:  # noqa: BLE001 - see `_get_reader`'s comment on why this is broad
            return "not installed"

    def supported_languages(self) -> list[str]:
        try:
            import easyocr

            # EasyOCR doesn't expose a single canonical "all supported codes"
            # list at import time without loading its language config; this
            # is the documented common set from its own README table.
            return (
                sorted(easyocr.Reader.lang_list) if hasattr(easyocr.Reader, "lang_list") else ["en"]
            )
        except Exception:  # noqa: BLE001
            return []

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            handwriting=True,
            tables=False,
            layout=False,
            gpu=True,
            batch_processing=True,
            multi_page_pdf=True,
        )

    def health_check(self) -> HealthCheckResult:
        try:
            import easyocr
            import torch
        except Exception as exc:  # noqa: BLE001 - see `_get_reader`'s comment on why this is broad
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
                detail=f"easyocr/torch could not be loaded: {exc}",
            )

        gpu_available = bool(getattr(torch, "cuda", None) and torch.cuda.is_available())
        detail = None
        ready = True
        if self.gpu and not gpu_available:
            detail = (
                "OCR_EASYOCR_GPU is enabled but no CUDA device is available — falling back to CPU."
            )

        return HealthCheckResult(
            provider_code=self.provider_code,
            installed=True,
            version=getattr(easyocr, "__version__", "unknown"),
            configured=True,
            authenticated=None,  # no auth concept — local model inference
            connectivity=None,  # no network dependency once models are cached locally
            dependencies_ok=True,
            gpu_available=gpu_available,
            ready=ready,
            detail=detail,
        )


def _union_box(boxes: list[BoundingBox]) -> BoundingBox:
    left = min(b.left for b in boxes)
    top = min(b.top for b in boxes)
    right = max(b.left + b.width for b in boxes)
    bottom = max(b.top + b.height for b in boxes)
    return BoundingBox(left=left, top=top, width=right - left, height=bottom - top)
