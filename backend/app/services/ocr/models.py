"""
Additive standardized OCR result shapes layered on top of `base.py`'s
existing `BoundingBox`/`OCRWordResult`/`OCRLineResult`/`OCRBlockResult`/
`OCRPageResult` (Page -> Block -> Line -> Word, per ADR-029).

Nothing here replaces or restructures those — `OCRResult`/`OCRBlock`/
`OCRLine`/`OCRWord` (the persisted DB hierarchy) stay exactly as ADR-029
decided. These are transient, in-memory-only shapes for capabilities that
don't have (and don't need) a dedicated DB table:

- `OCRParagraphResult` groups a block's lines by the engine's native
  paragraph boundary when it exposes one (e.g. Tesseract's `par_num`) —
  optional and additive on `OCRBlockResult` via `extract_paragraphs()`,
  never persisted, so it doesn't reopen ADR-029's "3 levels, not 4" call.
- `OCRTableResult`/`OCRLayoutRegion`/`OCRLayoutResult`/`OCRImageRegion`
  back the new `extract_tables()`/`extract_layout()`/`extract_images()`
  capability methods, which most engines (including Tesseract) don't
  support — see `ProviderCapabilities` below.
- `OCRDocumentResult` is the multi-page "Document" wrapper used by
  `extract_document()` for multi-page PDFs and by the benchmark module;
  the persisted equivalent of "a document" is `AnswerScript`/
  `OfficialExamDocument`, which already exist — this is just the
  in-memory aggregate passed between pipeline stages.
- `HealthCheckResult` backs `OCRProviderAdapter.health_check()` and the
  OCR Administration page's per-provider health panel.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from app.services.ocr.base import BoundingBox, OCRLineResult, OCRPageResult


@dataclass(frozen=True)
class OCRParagraphResult:
    """A block's lines grouped by the engine's native paragraph boundary.
    Purely a read-side convenience — never persisted (see module docstring)."""

    bounding_box: BoundingBox
    confidence: float
    reading_order: int
    lines: list[OCRLineResult] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


@dataclass(frozen=True)
class OCRTableCell:
    text: str
    row: int
    col: int
    row_span: int
    col_span: int
    bounding_box: BoundingBox
    confidence: float


@dataclass(frozen=True)
class OCRTableResult:
    bounding_box: BoundingBox
    confidence: float
    row_count: int
    col_count: int
    cells: list[OCRTableCell] = field(default_factory=list)


LayoutRegionType = Literal["title", "text", "table", "figure", "list", "header", "footer"]


@dataclass(frozen=True)
class OCRLayoutRegion:
    region_type: LayoutRegionType
    bounding_box: BoundingBox
    confidence: float
    reading_order: int


@dataclass(frozen=True)
class OCRLayoutResult:
    regions: list[OCRLayoutRegion] = field(default_factory=list)


@dataclass(frozen=True)
class OCRImageRegion:
    """An embedded figure/photo/diagram region detected within a page
    (distinct from the page image itself)."""

    bounding_box: BoundingBox
    confidence: float
    description: str | None = None


@dataclass(frozen=True)
class ProviderMetadata:
    provider_name: str
    provider_version: str
    processing_time_seconds: float | None
    raw_response: Any | None = None


@dataclass(frozen=True)
class OCRDocumentResult:
    """Multi-page aggregate — the in-memory "Document" level for
    `extract_document()` and the benchmark module. Not a new persisted
    entity: `AnswerScript`/`OfficialExamDocument` already are the
    document-level DB rows; this just carries their OCR output between
    pipeline stages before it's written page-by-page into `OCRResult`."""

    pages: list[OCRPageResult] = field(default_factory=list)
    metadata: ProviderMetadata | None = None

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def average_confidence(self) -> float:
        if not self.pages:
            return 0.0
        return sum(p.average_confidence for p in self.pages) / len(self.pages)


@dataclass
class HealthCheckResult:
    """Backs `OCRProviderAdapter.health_check()` and the OCR Administration
    page's per-provider health panel. Every field is best-effort — a
    provider that can't answer a given check (e.g. Tesseract has no
    concept of "authenticated") reports `None`, not a fabricated value."""

    provider_code: str
    installed: bool
    version: str | None
    configured: bool
    authenticated: bool | None
    connectivity: bool | None
    dependencies_ok: bool
    gpu_available: bool | None
    ready: bool
    detail: str | None = None


@dataclass(frozen=True)
class ProviderCapabilities:
    """What an adapter genuinely supports — drives whether the OCR
    Administration/Benchmark UI shows a capability as available or N/A,
    rather than silently returning an empty result and letting the UI
    misread "not supported" as "found nothing"."""

    handwriting: bool = False
    tables: bool = False
    layout: bool = False
    gpu: bool = False
    batch_processing: bool = False
    multi_page_pdf: bool = False
    key_value_pairs: bool = False
    selection_marks: bool = False
    signatures: bool = False
    queries: bool = False
