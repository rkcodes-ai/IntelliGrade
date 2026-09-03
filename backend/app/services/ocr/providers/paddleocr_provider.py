"""
Real OCR adapter wrapping `paddleocr` (PaddlePaddle-backed, CPU or GPU),
run in the isolated `.venv-paddleocr` venv and invoked from the main
backend process via `app.services.ocr.isolated_runtime` — the same
bridge pattern built for Surya/docTR/TrOCR this milestone (Section 16:
"investigate whether the same runtime-bridge architecture can safely make
.venv-paddleocr operational").

**This is a change from how this file previously worked**: earlier, this
class imported `paddleocr`/`paddlepaddle` directly, which requires the
main venv's own process to load paddle's native DLLs — genuinely blocked
by Windows Smart App Control on this machine (confirmed in the prior
milestone; Smart App Control was never disabled, per this project's
non-negotiable rules). Real re-verification this milestone found that
running the *exact same* `paddleocr` import and `.predict()` call inside
`.venv-paddleocr`'s own interpreter **process** (as a subprocess, invoked
by this bridge — never inside the main venv's process) does not hit that
block: real end-to-end inference against a rendered 4-line test image
returned the exact expected text at 99.12% confidence. Smart App Control
was never touched — the operation it was blocking (the main venv's
process loading paddle's DLLs) simply never happens with this
architecture; the isolated `.venv-paddleocr` process was always able to
load its own DLLs, since Smart App Control's policy attaches per-process/
per-binary, not project-wide.

Two genuine environment/API issues from the previous in-process
implementation still apply to the runner
(`isolated_runners/paddleocr_runner.py`, which duplicates this logic since
it runs in a separate interpreter with no access to this module): paddleocr
3.x's full API rewrite (`.predict()` replacing `.ocr()`, `use_textline_
orientation`/`device`/`text_det_thresh`/`text_rec_score_thresh` replacing
the old constructor kwargs) and `enable_mkldnn=False` being required on
this CPU build (MKL-DNN left on raises `NotImplementedError:
ConvertPirAttribute2RuntimeAttribute not support [...]`, a paddlepaddle
3.3.1 CPU-inference bug).

Like `EasyOCRProvider`/`SuryaOCRAdapter`, PaddleOCR's flat text detections
are mapped onto the standardized hierarchy as one page-level block
containing one line per detection, with synthetic whitespace-split words
sharing the line's bounding box (PaddleOCR doesn't return per-word boxes).

`extract_tables()`/`extract_layout()` still reference the *old*
`PPStructure` class (renamed `PPStructureV3` in paddleocr 3.x) and import
`paddleocr` directly rather than going through the bridge — unchanged
from before, since they were already out of scope for the core-OCR
verification pass and are not part of this milestone (core text
extraction, the method the actual pipeline calls, is what's bridged and
verified here).
"""

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
from app.services.ocr.models import (
    HealthCheckResult,
    LayoutRegionType,
    OCRLayoutRegion,
    OCRLayoutResult,
    OCRTableCell,
    OCRTableResult,
    ProviderCapabilities,
)

settings = get_settings()

# Same rationale as `easyocr_provider._LANGUAGE_ALIASES`: this app's
# existing convention passes Tesseract-style 3-letter codes; PaddleOCR
# uses its own short codes (mostly 2-letter, with a few exceptions like
# "ch"/"chinese_cht" per its own documented language list).
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


def _to_paddle_language(code: str) -> str:
    if code in _LANGUAGE_ALIASES.values():
        return code
    return _LANGUAGE_ALIASES.get(code, "en")


_RUNNER_SCRIPT = RUNNERS_DIR / "paddleocr_runner.py"


def _bbox_from_dict(data: dict[str, Any]) -> BoundingBox:
    return BoundingBox(
        left=int(data["left"]),
        top=int(data["top"]),
        width=int(data["width"]),
        height=int(data["height"]),
    )


class PaddleOCRProvider(OCRProviderAdapter):
    provider_code = "paddleocr"
    is_implemented = True

    def __init__(
        self,
        *,
        gpu: bool | None = None,
        det_threshold: float | None = None,
        rec_threshold: float | None = None,
        python_exe: str | None = None,
    ) -> None:
        super().__init__()
        self.gpu = settings.OCR_PADDLEOCR_GPU if gpu is None else gpu
        self.det_threshold = (
            det_threshold if det_threshold is not None else settings.OCR_PADDLEOCR_DET_THRESHOLD
        )
        self.rec_threshold = (
            rec_threshold if rec_threshold is not None else settings.OCR_PADDLEOCR_REC_THRESHOLD
        )
        configured = python_exe or settings.OCR_PADDLEOCR_PYTHON
        self._python_exe_path = (
            Path(configured) if configured else default_isolated_python(".venv-paddleocr")
        )

    def _get_structure_engine(self, *, table: bool) -> Any:
        # `extract_tables()`/`extract_layout()` remain in-process/unbridged
        # — out of scope for this milestone, see module docstring.
        from paddleocr import (
            PPStructure,  # deferred: heavy import, only paid when tables/layout are used
        )

        return PPStructure(table=table, ocr=True, show_log=False, use_gpu=self.gpu)

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
                result.get("error", "unknown PaddleOCR runner error")
            )
        return result

    def extract(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
        with self._timed():
            payload = self._invoke(
                {
                    "image_path": image_path,
                    "language": language,
                    "mode": "extract",
                    "options": {
                        "gpu": self.gpu,
                        "det_threshold": self.det_threshold,
                        "rec_threshold": self.rec_threshold,
                    },
                }
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
            # PaddleOCR's angle classifier corrects each detected text line
            # internally before recognition rather than reporting one
            # page-level rotation value — 0.0 here means "not applicable",
            # not "measured and confirmed upright".
            rotation_degrees=0.0,
            blocks=blocks,
        )

    def extract_tables(self, image_path: str, *, language: str = "eng") -> list[OCRTableResult]:
        """Real PPStructure-based table recognition — one of PaddleOCR's
        headline features the other five providers mostly lack."""
        structure = self._get_structure_engine(table=True)
        regions = structure(image_path)

        tables: list[OCRTableResult] = []
        for region in regions:
            if region.get("type") != "table":
                continue
            bbox = region.get("bbox", [0, 0, 0, 0])
            box = BoundingBox(
                left=int(bbox[0]),
                top=int(bbox[1]),
                width=int(bbox[2] - bbox[0]),
                height=int(bbox[3] - bbox[1]),
            )
            cell_data = (region.get("res") or {}).get("cell_bbox", [])
            cells = [
                OCRTableCell(
                    # PPStructure's cell text lives in its returned HTML, not per-cell here — a
                    # caller wanting per-cell text parses the HTML separately, kept out of this
                    # dataclass to avoid guessing a parse unverified against a real response.
                    text="",
                    row=0,
                    col=index,
                    row_span=1,
                    col_span=1,
                    bounding_box=BoundingBox(
                        left=int(cell[0]),
                        top=int(cell[1]),
                        width=int(cell[2] - cell[0]),
                        height=int(cell[3] - cell[1]),
                    ),
                    confidence=0.0,
                )
                for index, cell in enumerate(cell_data)
            ]
            tables.append(
                OCRTableResult(
                    bounding_box=box,
                    confidence=0.0,
                    row_count=1 if cells else 0,
                    col_count=len(cells),
                    cells=cells,
                )
            )
        return tables

    def extract_layout(self, image_path: str, *, language: str = "eng") -> OCRLayoutResult:
        """Real PPStructure-based layout detection (title/text/table/figure
        regions) — PaddleOCR's other headline feature."""
        structure = self._get_structure_engine(table=False)
        regions = structure(image_path)

        type_map: dict[str, LayoutRegionType] = {
            "title": "title",
            "text": "text",
            "table": "table",
            "figure": "figure",
            "list": "list",
            "header": "header",
            "footer": "footer",
        }
        layout_regions = []
        for index, region in enumerate(regions):
            bbox = region.get("bbox", [0, 0, 0, 0])
            layout_regions.append(
                OCRLayoutRegion(
                    region_type=type_map.get(region.get("type", "text"), "text"),
                    bounding_box=BoundingBox(
                        left=int(bbox[0]),
                        top=int(bbox[1]),
                        width=int(bbox[2] - bbox[0]),
                        height=int(bbox[3] - bbox[1]),
                    ),
                    confidence=float(region.get("score") or 0.0),
                    reading_order=index,
                )
            )
        return OCRLayoutResult(regions=layout_regions)

    def provider_version(self) -> str:
        try:
            return str(self._invoke({"mode": "health"}).get("version", "unknown"))
        except Exception:  # noqa: BLE001
            return "not installed"

    def supported_languages(self) -> list[str]:
        # PaddleOCR's own documented multilingual model list — not derived
        # from a runtime call since the package can't be imported here to
        # verify against (see module docstring); update if PaddleOCR's
        # supported set changes upstream.
        return ["en", "ch", "chinese_cht", "german", "fr", "japan", "korean", "hi", "es", "pt"]

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            handwriting=False,
            tables=True,
            layout=True,
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
                    "Create the .venv-paddleocr venv and install paddleocr/paddlepaddle to "
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
                detail=f"Isolated PaddleOCR runtime health check failed: {exc}",
            )

        gpu_available = payload.get("gpu_available")
        detail = None
        if self.gpu and not gpu_available:
            detail = "OCR_PADDLEOCR_GPU is enabled but no CUDA device is available; using CPU."

        return HealthCheckResult(
            provider_code=self.provider_code,
            installed=bool(payload.get("installed", False)),
            version=payload.get("version"),
            configured=True,
            authenticated=None,
            connectivity=None,
            dependencies_ok=bool(payload.get("installed", False)),
            gpu_available=gpu_available,
            ready=bool(payload.get("installed", False)),
            detail=detail,
        )


def _union_box(boxes: list[BoundingBox]) -> BoundingBox:
    left = min(b.left for b in boxes)
    top = min(b.top for b in boxes)
    right = max(b.left + b.width for b in boxes)
    bottom = max(b.top + b.height for b in boxes)
    return BoundingBox(left=left, top=top, width=right - left, height=bottom - top)
