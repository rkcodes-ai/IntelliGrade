"""
OCR provider adapter interface and result shapes.

Every engine (Tesseract, EasyOCR, PaddleOCR, Azure OCR, Google Vision, AWS
Textract) implements `OCRProviderAdapter.extract()` and returns the same
`OCRPageResult` shape, regardless of what the underlying engine's native
output looks like — this is what makes the pipeline/service layer (and the
`OCRResult`/`OCRBlock`/`OCRLine`/`OCRWord` persistence code) completely
engine-agnostic. See ADR-029 for why the hierarchy is
Page -> Block -> Line -> Word (not four levels with a separate Paragraph).

Module 12 (Enterprise Multi-OCR Platform) adds a richer capability surface
(`initialize`/`shutdown`/`health_check`/`extract_document`/`extract_pages`/
`extract_blocks`/`extract_paragraphs`/`extract_lines`/`extract_words`/
`extract_tables`/`extract_layout`/`extract_handwriting`/`extract_images`/
`confidence_score`/`supported_languages`/`provider_name`/`provider_version`/
`processing_time`) as **concrete methods with sensible defaults**, not new
abstract requirements — `extract()` stays the only method a provider must
implement. This means the five existing stub providers, and any external
code that only ever called `.extract()`, are unaffected; each provider
overrides only the methods where it's genuinely different from the default
(e.g. a provider with native table detection overrides `extract_tables()`
instead of inheriting the "not supported" default).
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    # Deferred to a TYPE_CHECKING-only import (rather than a top-level one)
    # because `models.py` imports from this module -- a real, unavoidable
    # circular import at runtime. `from __future__ import annotations` makes
    # every annotation in this file a lazily-evaluated string, so this is
    # safe: mypy resolves the names statically, nothing is imported at
    # runtime. See the individual methods below for the matching *runtime*
    # local imports they still need.
    from app.services.ocr.models import (
        HealthCheckResult,
        OCRDocumentResult,
        OCRImageRegion,
        OCRLayoutResult,
        OCRParagraphResult,
        OCRTableResult,
        ProviderCapabilities,
    )


@dataclass(frozen=True)
class BoundingBox:
    """Pixel coordinates, top-left origin — matches every engine's native convention."""

    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class OCRWordResult:
    text: str
    bounding_box: BoundingBox
    confidence: float  # 0-100
    reading_order: int


@dataclass(frozen=True)
class OCRLineResult:
    text: str
    bounding_box: BoundingBox
    confidence: float
    reading_order: int
    words: list[OCRWordResult] = field(default_factory=list)


@dataclass(frozen=True)
class OCRBlockResult:
    bounding_box: BoundingBox
    confidence: float
    reading_order: int
    # Best-effort layout classification — engines that can't distinguish
    # these (e.g. Tesseract's default page segmentation) always report "text".
    block_type: str = "text"  # "text" | "table" | "image"
    lines: list[OCRLineResult] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


@dataclass(frozen=True)
class OCRPageResult:
    raw_text: str
    average_confidence: float
    language: str
    rotation_degrees: float
    blocks: list[OCRBlockResult] = field(default_factory=list)


class OCRProviderAdapter(ABC):
    """One instance per OCR call — adapters are stateless beyond configuration.

    Only `extract()` is abstract. Everything below it is a concrete method
    with a working default, so a minimal provider needs to implement just
    one method (as the five pre-Module-12 stubs already did) while a full
    provider can override any subset of the richer surface."""

    provider_code: ClassVar[str]
    is_implemented: ClassVar[bool] = False

    def __init__(self) -> None:
        self._last_processing_time: float | None = None

    @abstractmethod
    def extract(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
        """Run OCR against a single page image and return its structured result.

        `image_path` is a local filesystem path (the pipeline downloads the
        page image from object storage to a temp file before calling this —
        no adapter talks to storage directly, keeping engine code and
        storage code independently swappable)."""
        raise NotImplementedError

    @contextmanager
    def _timed(self) -> Iterator[None]:
        """Wrap an `extract()` call's body with this to populate
        `processing_time()` — `with self._timed(): ...`. Optional: a
        provider that never calls this simply reports `processing_time()
        is None`, which is honest (no measurement taken), not a fabricated
        zero."""
        start = time.perf_counter()
        try:
            yield
        finally:
            self._last_processing_time = time.perf_counter() - start

    # --- Lifecycle -----------------------------------------------------

    def initialize(self) -> None:
        """Called once before first use — override to load models, open
        SDK clients, etc. Default: no-op (Tesseract and the cloud REST/SDK
        clients need no warm-up; EasyOCR/PaddleOCR override this to load
        their models once rather than per-call)."""
        return None

    def shutdown(self) -> None:
        """Release anything `initialize()` acquired. Default: no-op."""
        return None

    # --- Health ----------------------------------------------------------

    def health_check(self) -> HealthCheckResult:
        """Default reflection-only health check: reports whether this
        provider is implemented and importable, nothing more. Providers
        with a real SDK/binary/credentials override this to genuinely
        check version/config/auth/connectivity/GPU — see each provider's
        own `health_check()` for what it actually verifies."""
        from app.services.ocr.models import HealthCheckResult

        return HealthCheckResult(
            provider_code=self.provider_code,
            installed=self.is_implemented,
            version=self.provider_version() if self.is_implemented else None,
            configured=self.is_implemented,
            authenticated=None,
            connectivity=None,
            dependencies_ok=self.is_implemented,
            gpu_available=None,
            ready=self.is_implemented,
            detail=None if self.is_implemented else "Provider is registered but not implemented.",
        )

    # --- Multi-page / decomposition accessors ----------------------------
    #
    # These all funnel through `extract()` by default so a minimal provider
    # gets the full surface for free; a provider can override any of them
    # if its SDK offers a cheaper direct call for just that piece.

    def extract_document(
        self, file_paths: list[str], *, language: str = "eng"
    ) -> OCRDocumentResult:
        """Run `extract()` across every page of an already-split multi-page
        document (page splitting itself is the pipeline's job — see
        `app.services.image_processing`/`app.tasks.ocr_tasks` — this just
        aggregates already-split page paths into one `OCRDocumentResult`)."""
        from app.services.ocr.models import OCRDocumentResult, ProviderMetadata

        with self._timed():
            pages = [self.extract(path, language=language) for path in file_paths]
        return OCRDocumentResult(
            pages=pages,
            metadata=ProviderMetadata(
                provider_name=self.provider_name(),
                provider_version=self.provider_version(),
                processing_time_seconds=self.processing_time(),
            ),
        )

    def extract_pages(self, file_paths: list[str], *, language: str = "eng") -> list[OCRPageResult]:
        return [self.extract(path, language=language) for path in file_paths]

    def extract_blocks(self, image_path: str, *, language: str = "eng") -> list[OCRBlockResult]:
        return self.extract(image_path, language=language).blocks

    def extract_paragraphs(
        self, image_path: str, *, language: str = "eng"
    ) -> list[OCRParagraphResult]:
        """Default: one paragraph per block (most engines, including
        Tesseract's default `extract()` grouping, don't separately expose
        paragraph boundaries within a block — see ADR-029). A provider
        whose native output distinguishes paragraphs overrides this."""
        from app.services.ocr.models import OCRParagraphResult

        paragraphs: list[OCRParagraphResult] = []
        for block in self.extract_blocks(image_path, language=language):
            paragraphs.append(
                OCRParagraphResult(
                    bounding_box=block.bounding_box,
                    confidence=block.confidence,
                    reading_order=block.reading_order,
                    lines=block.lines,
                )
            )
        return paragraphs

    def extract_lines(self, image_path: str, *, language: str = "eng") -> list[OCRLineResult]:
        return [
            line
            for block in self.extract_blocks(image_path, language=language)
            for line in block.lines
        ]

    def extract_words(self, image_path: str, *, language: str = "eng") -> list[OCRWordResult]:
        return [
            word
            for line in self.extract_lines(image_path, language=language)
            for word in line.words
        ]

    # --- Capabilities most engines don't have — default to "unsupported",
    # never a fabricated result. ------------------------------------------

    def extract_tables(self, image_path: str, *, language: str = "eng") -> list[OCRTableResult]:
        """Default: no table detection. Providers with real table
        recognition (PaddleOCR, Azure Layout API, AWS Textract
        AnalyzeDocument) override this."""
        return []

    def extract_layout(self, image_path: str, *, language: str = "eng") -> OCRLayoutResult:
        """Default: one "text" region per block — a trivial layout, not a
        fabricated multi-class one. Providers with real layout detection
        (PaddleOCR, Azure Layout API) override this."""
        from app.services.ocr.models import OCRLayoutRegion, OCRLayoutResult

        regions = [
            OCRLayoutRegion(
                region_type="text",
                bounding_box=block.bounding_box,
                confidence=block.confidence,
                reading_order=block.reading_order,
            )
            for block in self.extract_blocks(image_path, language=language)
        ]
        return OCRLayoutResult(regions=regions)

    def extract_handwriting(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
        """Default: delegate to `extract()` as a best effort (some engines
        use the same call path for print and handwriting). Providers with
        a dedicated handwriting mode/model override this."""
        return self.extract(image_path, language=language)

    def extract_images(self, image_path: str) -> list[OCRImageRegion]:
        """Default: no embedded-figure detection."""
        return []

    # --- Metadata ---------------------------------------------------------

    def confidence_score(self, result: OCRPageResult) -> float:
        return result.average_confidence

    def supported_languages(self) -> list[str]:
        """Default: English only. Every real provider overrides this with
        its actual documented/installed language list — never a guessed
        list, see each provider's own implementation."""
        return ["eng"]

    def provider_name(self) -> str:
        return self.provider_code

    def provider_version(self) -> str:
        return "unknown"

    def processing_time(self) -> float | None:
        """Seconds taken by the most recent `extract()`/`extract_document()`
        call that used `self._timed()`. `None` if nothing has run yet or
        the provider doesn't instrument timing."""
        return self._last_processing_time

    def capabilities(self) -> ProviderCapabilities:
        """What this provider genuinely supports — see
        `app.services.ocr.models.ProviderCapabilities`. Default: the bare
        minimum (no GPU, no tables, no layout, no handwriting)."""
        from app.services.ocr.models import ProviderCapabilities

        return ProviderCapabilities()
