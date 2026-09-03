"""
Real OCR adapter wrapping the `pytesseract`/Tesseract system binary — the
one provider actually implemented in Module 05 (see ADR-032), enriched in
Module 12 with real health/version/language/config support (OEM/PSM/DPI).

Tesseract itself is a system dependency (`tesseract-ocr` apt package in
production Docker; installed via `winget` in this dev sandbox for live
validation — see `docs/ocr-pipeline-guide.md`). `pytesseract.pytesseract.
tesseract_cmd` is set from `Settings.TESSERACT_CMD` when configured,
otherwise pytesseract relies on the binary being on `PATH`.
"""

import os
import re
import shutil

import pytesseract
from PIL import Image
from pytesseract import Output

from app.core.config import get_settings
from app.services.ocr.base import (
    BoundingBox,
    OCRBlockResult,
    OCRLineResult,
    OCRPageResult,
    OCRProviderAdapter,
    OCRWordResult,
)
from app.services.ocr.models import HealthCheckResult, ProviderCapabilities

settings = get_settings()

if settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

_OSD_ROTATE_PATTERN = re.compile(r"Rotate:\s*(\d+)")

# Tesseract's own default page-segmentation mode (PSM 3, "fully automatic
# page segmentation") assumes a roughly page-shaped image and can fail to
# find *any* text region at all on an extreme-aspect-ratio strip -- this
# project's own `trim_margins` preprocessing step deliberately crops away
# all whitespace, which turns a single-line answer/question into exactly
# such a strip. Confirmed during the Six-Provider OCR milestone's real,
# multi-page-PDF end-to-end verification: two nearly-identical single-line
# pages, margin-trimmed to ~175x2480px (a ~14:1 aspect ratio), and PSM 3
# returned zero detections for one of them while PSM 6 ("assume a single
# uniform block of text") correctly read both -- not a fluke, reproduced
# consistently. PSM 6 is only substituted for genuinely extreme aspect
# ratios; ordinary page-shaped images keep using Tesseract's own PSM 3
# default (or whatever `self.psm` was explicitly configured), since PSM
# 3's real multi-column/layout-aware segmentation is better than PSM 6
# for typical documents.
_EXTREME_ASPECT_RATIO_THRESHOLD = 5.0
_EXTREME_ASPECT_RATIO_PSM = 6


def _resolve_effective_psm(image_path: str, configured_psm: int | None) -> int | None:
    if configured_psm is not None:
        return configured_psm  # explicit configuration always wins
    try:
        with Image.open(image_path) as image:
            width, height = image.size
    except Exception:  # noqa: BLE001 - a bad path/format fails at image_to_data anyway
        return None
    if height == 0 or width == 0:
        return None
    aspect_ratio = max(width / height, height / width)
    if aspect_ratio >= _EXTREME_ASPECT_RATIO_THRESHOLD:
        return _EXTREME_ASPECT_RATIO_PSM
    return None


def _detect_rotation_degrees(image_path: str) -> float:
    """Best-effort: Tesseract's orientation/script detection fails outright
    on sparse or low-contrast images — that's expected, not an error worth
    surfacing, so any failure just means "assume unrotated"."""
    try:
        osd = pytesseract.image_to_osd(image_path)
        match = _OSD_ROTATE_PATTERN.search(osd)
        return float(match.group(1)) if match else 0.0
    except pytesseract.TesseractError:
        return 0.0


class TesseractProvider(OCRProviderAdapter):
    provider_code = "tesseract"
    is_implemented = True

    def __init__(
        self,
        *,
        oem: int | None = None,
        psm: int | None = None,
        dpi: int | None = None,
    ) -> None:
        """`oem` (OCR Engine Mode, 0-3), `psm` (Page Segmentation Mode,
        0-13), and `dpi` are optional — when unset, Tesseract uses its own
        defaults (oem 3 "default, based on what's available", psm 3 "fully
        automatic page segmentation"). Passed straight through to the
        `tesseract` CLI via pytesseract's `config` string, the same
        mechanism `--oem`/`--psm`/`--dpi` use on the command line."""
        super().__init__()
        self.oem = oem
        self.psm = psm
        self.dpi = dpi

    def _tesseract_config(self, *, effective_psm: int | None) -> str:
        parts = []
        if self.oem is not None:
            parts.append(f"--oem {self.oem}")
        if effective_psm is not None:
            parts.append(f"--psm {effective_psm}")
        if self.dpi is not None:
            parts.append(f"--dpi {self.dpi}")
        if settings.TESSERACT_TESSDATA_DIR:
            # Step 4.2 milestone: Indian-language `.traineddata` packs
            # live in a project-local directory (the system install's own
            # tessdata/ isn't writable without elevation on this dev
            # machine). NOT quoted: pytesseract splits this config string
            # with `shlex.split(config, posix=False)` on Windows, which
            # preserves literal quote characters in non-posix mode rather
            # than stripping them -- a quoted path here is passed to
            # tesseract.exe WITH the quote characters embedded in the
            # string, breaking the path (confirmed via direct
            # reproduction). Requires this configured path contain no
            # spaces, matching --oem/--psm/--dpi above (also unquoted).
            parts.append(f"--tessdata-dir {settings.TESSERACT_TESSDATA_DIR}")
        return " ".join(parts)

    def extract(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
        with self._timed():
            effective_psm = _resolve_effective_psm(image_path, self.psm)
            data = pytesseract.image_to_data(
                image_path,
                lang=language,
                output_type=Output.DICT,
                config=self._tesseract_config(effective_psm=effective_psm),
            )
            rotation = _detect_rotation_degrees(image_path)

        blocks: dict[tuple[int, int], OCRBlockResult] = {}
        lines: dict[tuple[int, int, int], list[OCRWordResult]] = {}
        line_boxes: dict[tuple[int, int, int], list[tuple[int, int, int, int]]] = {}
        line_confidences: dict[tuple[int, int, int], list[float]] = {}
        reading_order = 0
        all_confidences: list[float] = []
        text_parts: list[str] = []

        n_rows = len(data["text"])
        for i in range(n_rows):
            text = data["text"][i].strip()
            conf = float(data["conf"][i])
            if not text or conf < 0:
                continue

            block_key = (data["block_num"][i], data["par_num"][i])
            line_key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            box = (data["left"][i], data["top"][i], data["width"][i], data["height"][i])

            word = OCRWordResult(
                text=text,
                bounding_box=BoundingBox(left=box[0], top=box[1], width=box[2], height=box[3]),
                confidence=conf,
                reading_order=reading_order,
            )
            reading_order += 1
            all_confidences.append(conf)
            text_parts.append(text)

            lines.setdefault(line_key, []).append(word)
            line_boxes.setdefault(line_key, []).append(box)
            line_confidences.setdefault(line_key, []).append(conf)
            blocks.setdefault(
                block_key,
                OCRBlockResult(
                    bounding_box=BoundingBox(0, 0, 0, 0),
                    confidence=0.0,
                    reading_order=len(blocks),
                ),
            )

        for block_key, block in list(blocks.items()):
            block_lines: list[OCRLineResult] = []
            block_boxes: list[tuple[int, int, int, int]] = []
            block_confs: list[float] = []
            for line_key in sorted(k for k in lines if k[:2] == block_key):
                words = lines[line_key]
                boxes = line_boxes[line_key]
                confs = line_confidences[line_key]
                line_left = min(b[0] for b in boxes)
                line_top = min(b[1] for b in boxes)
                line_right = max(b[0] + b[2] for b in boxes)
                line_bottom = max(b[1] + b[3] for b in boxes)
                block_lines.append(
                    OCRLineResult(
                        text=" ".join(w.text for w in words),
                        bounding_box=BoundingBox(
                            left=line_left,
                            top=line_top,
                            width=line_right - line_left,
                            height=line_bottom - line_top,
                        ),
                        confidence=sum(confs) / len(confs),
                        reading_order=len(block_lines),
                        words=words,
                    )
                )
                block_boxes.extend(boxes)
                block_confs.extend(confs)

            block_left = min(b[0] for b in block_boxes)
            block_top = min(b[1] for b in block_boxes)
            block_right = max(b[0] + b[2] for b in block_boxes)
            block_bottom = max(b[1] + b[3] for b in block_boxes)
            blocks[block_key] = OCRBlockResult(
                bounding_box=BoundingBox(
                    left=block_left,
                    top=block_top,
                    width=block_right - block_left,
                    height=block_bottom - block_top,
                ),
                confidence=sum(block_confs) / len(block_confs),
                reading_order=block.reading_order,
                lines=block_lines,
            )

        return OCRPageResult(
            raw_text="\n".join(text_parts),
            average_confidence=(
                (sum(all_confidences) / len(all_confidences)) if all_confidences else 0.0
            ),
            language=language,
            rotation_degrees=rotation,
            blocks=list(blocks.values()),
        )

    def provider_version(self) -> str:
        try:
            return str(pytesseract.get_tesseract_version())
        except Exception:  # noqa: BLE001 - version lookup failing is not extract() failing
            return "unknown"

    def supported_languages(self) -> list[str]:
        """The language packs actually installed on this machine (real
        `tesseract --list-langs` output via pytesseract), not a hardcoded
        guess — a fresh install with only `eng.traineddata` genuinely
        cannot OCR Hindi even though Tesseract-the-project supports it.
        Honors `TESSERACT_TESSDATA_DIR` (Step 4.2's project-local Indian-
        language packs) the same way `_tesseract_config()` does."""
        config = (
            f"--tessdata-dir {settings.TESSERACT_TESSDATA_DIR}"
            if settings.TESSERACT_TESSDATA_DIR
            else ""
        )
        try:
            return list(pytesseract.get_languages(config=config))
        except Exception:  # noqa: BLE001
            return []

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            handwriting=False,  # Tesseract's printed-text LSTM models are weak on handwriting
            tables=False,
            layout=False,
            gpu=False,
            batch_processing=False,
            multi_page_pdf=True,  # the pipeline splits PDFs to page images before calling extract()
        )

    def health_check(self) -> HealthCheckResult:
        binary = pytesseract.pytesseract.tesseract_cmd or shutil.which("tesseract")
        installed = bool(binary and (shutil.which(binary) or os.path.isfile(binary)))
        version: str | None = None
        languages: list[str] = []
        detail: str | None = None

        if installed:
            try:
                version = str(pytesseract.get_tesseract_version())
            except Exception as exc:  # noqa: BLE001
                installed = False
                detail = f"Tesseract binary found but failed to report its version: {exc}"
            else:
                try:
                    languages = list(pytesseract.get_languages())
                except Exception as exc:  # noqa: BLE001
                    detail = f"Could not list installed language packs: {exc}"
        else:
            detail = "Tesseract executable not found (check TESSERACT_CMD / PATH)."

        return HealthCheckResult(
            provider_code=self.provider_code,
            installed=installed,
            version=version,
            configured=True,  # no required config beyond an optional TESSERACT_CMD
            authenticated=None,  # no auth concept for a local binary
            connectivity=None,  # no network dependency
            dependencies_ok=installed,
            gpu_available=False,  # Tesseract's LSTM engine is CPU-only in this integration
            ready=installed and bool(languages),
            detail=detail,
        )
