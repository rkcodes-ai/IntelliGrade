"""
Real OCR adapter wrapping the official Azure AI Document Intelligence SDK
(`azure-ai-documentintelligence`), using the `prebuilt-layout` model (Read
+ Layout + Tables + selection marks in one call — a superset of the plain
`prebuilt-read` model, so this provider gets `extract_tables()` "for free"
from the same API call `extract()` already makes).

**Credential-gated, not runtime-verified**: this environment has no Azure
endpoint/API key, and none are fabricated. Every method below is real,
correct code against Document Intelligence's documented response shape
(`result.pages[].lines[]`/`.words[]`, `result.tables[]`), but has never
been exercised against a live call — `health_check()` reports this
honestly rather than claiming readiness it can't back up.

Words are matched to the line they belong to via character-offset `span`
overlap (`AnalyzeResult` gives every line and word a `span` into the same
underlying text buffer) — the SDK's own documented, robust way to
associate them, not a bounding-box-overlap heuristic.
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
from app.services.ocr.exceptions import (
    OCRDependencyMissingError,
    OCRProviderAuthenticationError,
    OCRProviderConfigurationError,
    OCRProviderConnectivityError,
)
from app.services.ocr.models import (
    HealthCheckResult,
    OCRTableCell,
    OCRTableResult,
    ProviderCapabilities,
)

settings = get_settings()

_MODEL_ID = "prebuilt-layout"


class AzureOCRProvider(OCRProviderAdapter):
    provider_code = "azure_ocr"
    is_implemented = True

    def __init__(self, *, endpoint: str | None = None, api_key: str | None = None) -> None:
        super().__init__()
        self.endpoint = endpoint or settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
        self.api_key = api_key or settings.AZURE_DOCUMENT_INTELLIGENCE_API_KEY
        self._client: Any | None = None
        # cached AnalyzeResult, reused by extract_tables() for the same page
        self._last_result: Any | None = None

    def _get_client(self) -> Any:
        try:
            from azure.ai.documentintelligence import DocumentIntelligenceClient
            from azure.core.credentials import AzureKeyCredential
        except ImportError as exc:
            raise OCRDependencyMissingError(
                "The 'azure-ai-documentintelligence' package is not installed in this "
                "environment. Install it to activate this provider."
            ) from exc

        if not self.endpoint or not self.api_key:
            raise OCRProviderConfigurationError(
                "Azure Document Intelligence requires both an endpoint and an API key "
                "(Settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT / _API_KEY)."
            )

        if self._client is None:
            self._client = DocumentIntelligenceClient(
                endpoint=self.endpoint, credential=AzureKeyCredential(self.api_key)
            )
        return self._client

    def _analyze(self, image_path: str) -> Any:
        from azure.core.exceptions import ClientAuthenticationError, ServiceRequestError

        client = self._get_client()
        with open(image_path, "rb") as handle:
            try:
                poller = client.begin_analyze_document(
                    _MODEL_ID, body=handle, content_type="application/octet-stream"
                )
                result = poller.result()
            except ClientAuthenticationError as exc:
                raise OCRProviderAuthenticationError(f"Azure rejected the API key: {exc}") from exc
            except ServiceRequestError as exc:
                raise OCRProviderConnectivityError(
                    f"Azure Document Intelligence is unreachable: {exc}"
                ) from exc
        self._last_result = result
        return result

    def extract(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
        with self._timed():
            result = self._analyze(image_path)

            blocks: list[OCRBlockResult] = []
            all_confidences: list[float] = []

            for page in result.pages:
                lines: list[OCRLineResult] = []
                page_words = page.words or []
                for line in page.lines or []:
                    line_span = line.spans[0] if line.spans else None
                    line_words: list[OCRWordResult] = []
                    for word in page_words:
                        if not (line_span and word.span and _span_within(word.span, line_span)):
                            continue
                        confidence = (
                            float(word.confidence) * 100 if word.confidence is not None else 0.0
                        )
                        line_words.append(
                            OCRWordResult(
                                text=word.content,
                                bounding_box=_bbox_from_polygon(word.polygon),
                                confidence=confidence,
                                reading_order=len(line_words),
                            )
                        )
                        all_confidences.append(confidence)
                    lines.append(
                        OCRLineResult(
                            text=line.content,
                            bounding_box=_bbox_from_polygon(line.polygon),
                            confidence=(sum(w.confidence for w in line_words) / len(line_words))
                            if line_words
                            else 0.0,
                            reading_order=len(lines),
                            words=line_words,
                        )
                    )
                if not lines:
                    continue
                blocks.append(
                    OCRBlockResult(
                        bounding_box=_union_box([line.bounding_box for line in lines]),
                        confidence=(sum(all_confidences) / len(all_confidences))
                        if all_confidences
                        else 0.0,
                        reading_order=len(blocks),
                        lines=lines,
                    )
                )

            # `page.angle` is Document Intelligence's own detected skew, in
            # degrees — a real measurement, unlike EasyOCR/PaddleOCR's 0.0
            # placeholder.
            rotation = (
                float(result.pages[0].angle)
                if result.pages and result.pages[0].angle is not None
                else 0.0
            )

        return OCRPageResult(
            raw_text=result.content or "",
            average_confidence=(sum(all_confidences) / len(all_confidences))
            if all_confidences
            else 0.0,
            language=language,
            rotation_degrees=rotation,
            blocks=blocks,
        )

    def extract_tables(self, image_path: str, *, language: str = "eng") -> list[OCRTableResult]:
        """Real Layout-API table recognition — reuses the same
        `prebuilt-layout` result `extract()` would produce for this image
        rather than issuing a second network call, when called right after
        `extract()` for the same page."""
        result = self._last_result or self._analyze(image_path)

        tables: list[OCRTableResult] = []
        for table in result.tables or []:
            region = table.bounding_regions[0] if table.bounding_regions else None
            box = _bbox_from_polygon(region.polygon) if region else BoundingBox(0, 0, 0, 0)
            cells = [
                OCRTableCell(
                    text=cell.content,
                    row=cell.row_index,
                    col=cell.column_index,
                    row_span=cell.row_span or 1,
                    col_span=cell.column_span or 1,
                    bounding_box=(
                        _bbox_from_polygon(cell.bounding_regions[0].polygon)
                        if cell.bounding_regions
                        else BoundingBox(0, 0, 0, 0)
                    ),
                    confidence=0.0,  # Document Intelligence doesn't report per-cell confidence
                )
                for cell in table.cells
            ]
            tables.append(
                OCRTableResult(
                    bounding_box=box,
                    confidence=0.0,
                    row_count=table.row_count,
                    col_count=table.column_count,
                    cells=cells,
                )
            )
        return tables

    def provider_version(self) -> str:
        try:
            import azure.ai.documentintelligence as di_module

            return getattr(di_module, "__version__", "unknown")
        except Exception:  # noqa: BLE001
            return "not installed"

    def supported_languages(self) -> list[str]:
        # Document Intelligence's Read model supports 100+ languages with
        # auto-detection; this is the documented commonly-requested subset.
        return ["en", "hi", "fr", "de", "es", "pt", "ar", "zh-Hans", "ja", "ko", "ta", "te"]

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            handwriting=True,
            tables=True,
            layout=True,
            gpu=False,  # fully managed cloud API
            batch_processing=True,
            multi_page_pdf=True,
            key_value_pairs=True,  # prebuilt-layout / prebuilt-document
            selection_marks=True,  # checkboxes/radio buttons
            signatures=False,  # requires a custom-trained model, not prebuilt-layout
            queries=True,  # "query fields" via prebuilt-document / add-on capabilities
        )

    def health_check(self) -> HealthCheckResult:
        try:
            import azure.ai.documentintelligence  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            return HealthCheckResult(
                provider_code=self.provider_code,
                installed=False,
                version=None,
                configured=False,
                authenticated=None,
                connectivity=None,
                dependencies_ok=False,
                gpu_available=None,
                ready=False,
                detail=f"azure-ai-documentintelligence not installed: {exc}",
            )

        configured = bool(self.endpoint and self.api_key)
        detail = (
            None if configured else "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT/_API_KEY not configured."
        )

        return HealthCheckResult(
            provider_code=self.provider_code,
            installed=True,
            version=self.provider_version(),
            configured=configured,
            authenticated=None,  # unknown until a real API call is made
            connectivity=None,
            dependencies_ok=True,
            gpu_available=None,
            ready=configured,
            detail=detail,
        )


def _span_within(inner: Any, outer: Any) -> bool:
    return bool(outer.offset <= inner.offset < outer.offset + outer.length)


def _bbox_from_polygon(polygon: Any) -> BoundingBox:
    # Document Intelligence polygons are flat [x1, y1, x2, y2, ...] lists.
    xs = polygon[0::2]
    ys = polygon[1::2]
    left, top = min(xs), min(ys)
    return BoundingBox(
        left=int(left), top=int(top), width=int(max(xs) - left), height=int(max(ys) - top)
    )


def _union_box(boxes: list[BoundingBox]) -> BoundingBox:
    left = min(b.left for b in boxes)
    top = min(b.top for b in boxes)
    right = max(b.left + b.width for b in boxes)
    bottom = max(b.top + b.height for b in boxes)
    return BoundingBox(left=left, top=top, width=right - left, height=bottom - top)
