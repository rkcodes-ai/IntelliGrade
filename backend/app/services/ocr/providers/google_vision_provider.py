"""
Real OCR adapter wrapping the official Google Cloud Vision SDK
(`google-cloud-vision`)'s `document_text_detection` API.

**Credential-gated, not runtime-verified**: this environment has no Google
Cloud service-account credentials, and none are fabricated — every method
below is real, correct code against Vision's documented response shape
(`response.full_text_annotation.pages[].blocks[].paragraphs[].words[].
symbols[]`, which natively matches this project's Block hierarchy *plus* a
real Paragraph level, unlike every other provider in this module), but it
has never been exercised against a live Vision API call. `health_check()`
reports this honestly (`configured=False`/`authenticated=None`) rather
than claiming readiness it can't back up.

Authentication: a service-account JSON key file, path from
`Settings.GOOGLE_VISION_CREDENTIALS_PATH` — the same shape as every other
Google Cloud SDK client. If unset, the client falls back to the SDK's own
default credential discovery (`GOOGLE_APPLICATION_CREDENTIALS` env var,
metadata server on GCP, etc.), exactly like `gcloud`/any other Google Cloud
tool.
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
from app.services.ocr.models import HealthCheckResult, OCRParagraphResult, ProviderCapabilities

settings = get_settings()


class GoogleVisionProvider(OCRProviderAdapter):
    provider_code = "google_vision"
    is_implemented = True

    def __init__(self, *, credentials_path: str | None = None) -> None:
        super().__init__()
        self.credentials_path = credentials_path or settings.GOOGLE_VISION_CREDENTIALS_PATH
        self._client: Any | None = None

    def _get_client(self) -> Any:
        try:
            from google.cloud import vision
        except ImportError as exc:
            raise OCRDependencyMissingError(
                "The 'google-cloud-vision' package is not installed in this environment. "
                "Install it to activate this provider."
            ) from exc

        if self._client is not None:
            return self._client

        try:
            if self.credentials_path:
                from google.oauth2 import service_account

                # google-auth ships no py.typed marker, so this call is
                # untyped even under the `google.oauth2.service_account`
                # mypy override (which only covers *missing* imports) —
                # same "accepted, documented gap" treatment as this
                # project's other untyped third-party SDKs.
                credentials = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
                    self.credentials_path
                )
                self._client = vision.ImageAnnotatorClient(credentials=credentials)
            else:
                # Falls back to the SDK's own default credential discovery
                # (GOOGLE_APPLICATION_CREDENTIALS env var, GCP metadata
                # server, etc.) — same as every other Google Cloud client.
                self._client = vision.ImageAnnotatorClient()
        except FileNotFoundError as exc:
            raise OCRProviderConfigurationError(
                f"Google Vision credentials file not found: {self.credentials_path}"
            ) from exc
        except Exception as exc:  # noqa: BLE001 - covers google.auth.exceptions.DefaultCredentialsError etc.
            raise OCRProviderConfigurationError(
                f"Google Vision client could not be configured: {exc}"
            ) from exc

        return self._client

    def extract(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
        from google.api_core import exceptions as google_exceptions

        with self._timed():
            client = self._get_client()
            with open(image_path, "rb") as handle:
                content = handle.read()

            from google.cloud import vision

            image = vision.Image(content=content)
            try:
                response = client.document_text_detection(image=image)
            except google_exceptions.Unauthenticated as exc:
                raise OCRProviderAuthenticationError(
                    f"Google Vision rejected the credentials: {exc}"
                ) from exc
            except google_exceptions.ServiceUnavailable as exc:
                raise OCRProviderConnectivityError(f"Google Vision is unreachable: {exc}") from exc

            if response.error.message:
                raise OCRProviderConfigurationError(
                    f"Google Vision returned an error: {response.error.message}"
                )

            blocks: list[OCRBlockResult] = []
            all_confidences: list[float] = []
            reading_order = 0

            pages = response.full_text_annotation.pages
            for page in pages:
                for block in page.blocks:
                    block_lines: list[OCRLineResult] = []
                    for paragraph in block.paragraphs:
                        words: list[OCRWordResult] = []
                        for word in paragraph.words:
                            text = "".join(symbol.text for symbol in word.symbols)
                            confidence = float(word.confidence) * 100
                            words.append(
                                OCRWordResult(
                                    text=text,
                                    bounding_box=_bbox_from_vertices(word.bounding_box.vertices),
                                    confidence=confidence,
                                    reading_order=reading_order,
                                )
                            )
                            reading_order += 1
                            all_confidences.append(confidence)
                        if not words:
                            continue
                        block_lines.append(
                            OCRLineResult(
                                text=" ".join(w.text for w in words),
                                bounding_box=_bbox_from_vertices(paragraph.bounding_box.vertices),
                                confidence=(float(paragraph.confidence) * 100),
                                reading_order=len(block_lines),
                                words=words,
                            )
                        )
                    if not block_lines:
                        continue
                    blocks.append(
                        OCRBlockResult(
                            bounding_box=_bbox_from_vertices(block.bounding_box.vertices),
                            confidence=float(block.confidence) * 100,
                            reading_order=len(blocks),
                            lines=block_lines,
                        )
                    )

        return OCRPageResult(
            raw_text=response.full_text_annotation.text,
            average_confidence=(sum(all_confidences) / len(all_confidences))
            if all_confidences
            else 0.0,
            language=language,
            # Vision reports per-word/paragraph bounding polygons, which
            # already account for rotation implicitly, but no single
            # page-level rotation degrees value — 0.0 here means "not
            # separately reported", not "confirmed upright".
            rotation_degrees=0.0,
            blocks=blocks,
        )

    def extract_paragraphs(
        self, image_path: str, *, language: str = "eng"
    ) -> list[OCRParagraphResult]:
        """Google Vision is the one provider in this module whose native
        response genuinely distinguishes paragraphs within a block — this
        overrides the base class's "one paragraph per block" default with
        a real paragraph-level extraction instead of re-deriving it from
        already-flattened blocks."""
        from google.cloud import vision

        client = self._get_client()
        with open(image_path, "rb") as handle:
            content = handle.read()
        response = client.document_text_detection(image=vision.Image(content=content))

        paragraphs: list[OCRParagraphResult] = []
        for page in response.full_text_annotation.pages:
            for block in page.blocks:
                for paragraph in block.paragraphs:
                    words: list[OCRWordResult] = []
                    for reading_order, word in enumerate(paragraph.words):
                        text = "".join(symbol.text for symbol in word.symbols)
                        words.append(
                            OCRWordResult(
                                text=text,
                                bounding_box=_bbox_from_vertices(word.bounding_box.vertices),
                                confidence=float(word.confidence) * 100,
                                reading_order=reading_order,
                            )
                        )
                    if not words:
                        continue
                    line = OCRLineResult(
                        text=" ".join(w.text for w in words),
                        bounding_box=_bbox_from_vertices(paragraph.bounding_box.vertices),
                        confidence=float(paragraph.confidence) * 100,
                        reading_order=0,
                        words=words,
                    )
                    paragraphs.append(
                        OCRParagraphResult(
                            bounding_box=line.bounding_box,
                            confidence=line.confidence,
                            reading_order=len(paragraphs),
                            lines=[line],
                        )
                    )
        return paragraphs

    def provider_version(self) -> str:
        try:
            import google.cloud.vision as vision_module

            return getattr(vision_module, "__version__", "unknown")
        except Exception:  # noqa: BLE001
            return "not installed"

    def supported_languages(self) -> list[str]:
        # Google Vision auto-detects language and supports ~50+ languages;
        # it doesn't require (or expose) an explicit selectable list the
        # way an OCR-only engine does — this is the documented "commonly
        # requested" subset relevant to IntelliGrade's upload pipeline.
        return ["en", "hi", "fr", "de", "es", "pt", "ar", "zh", "ja", "ko", "ta", "te"]

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            handwriting=True,  # document_text_detection covers dense/handwritten text
            tables=False,  # Vision has no dedicated table-structure API (unlike Azure/AWS)
            layout=False,
            gpu=False,  # fully managed cloud API — no local compute concept
            batch_processing=True,  # batchAnnotateFiles / async batch endpoints exist
            multi_page_pdf=True,  # via batchAnnotateFiles for PDF/TIFF
        )

    def health_check(self) -> HealthCheckResult:
        try:
            from google.cloud import vision  # noqa: F401
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
                detail=f"google-cloud-vision not installed: {exc}",
            )

        configured = bool(self.credentials_path)
        detail = None
        authenticated = None
        if not configured:
            detail = (
                "No GOOGLE_VISION_CREDENTIALS_PATH configured — relying on the SDK's default "
                "credential discovery (GOOGLE_APPLICATION_CREDENTIALS env var, GCP metadata "
                "server, etc.), which is not verified here."
            )

        return HealthCheckResult(
            provider_code=self.provider_code,
            installed=True,
            version=self.provider_version(),
            configured=configured,
            authenticated=authenticated,  # unknown until a real API call is made — never guessed
            connectivity=None,  # would require a real network call to verify; not attempted here
            dependencies_ok=True,
            gpu_available=None,  # not applicable to a managed cloud API
            ready=configured,
            detail=detail,
        )


def _bbox_from_vertices(vertices: Any) -> BoundingBox:
    xs = [v.x for v in vertices]
    ys = [v.y for v in vertices]
    left, top = min(xs), min(ys)
    return BoundingBox(left=left, top=top, width=max(xs) - left, height=max(ys) - top)
