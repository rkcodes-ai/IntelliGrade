"""
Provider-code -> adapter-class registry. `OCRProvider` (the DB lookup
table, seeded by migration `0009_seed_ocr_providers.py`) stores the same
codes as data — this module is the code-side half of ADR-028's "global
system catalog" design: the DB row says a provider *exists and is
enabled*; this registry says whether code actually backs it.
"""

from app.services.ocr.base import OCRProviderAdapter
from app.services.ocr.providers.aws_textract_provider import AWSTextractProvider
from app.services.ocr.providers.azure_provider import AzureOCRProvider
from app.services.ocr.providers.doctr_provider import DocTROCRAdapter
from app.services.ocr.providers.easyocr_provider import EasyOCRProvider
from app.services.ocr.providers.google_vision_provider import GoogleVisionProvider
from app.services.ocr.providers.paddleocr_provider import PaddleOCRProvider
from app.services.ocr.providers.surya_provider import SuryaOCRAdapter
from app.services.ocr.providers.tesseract_provider import TesseractProvider
from app.services.ocr.providers.trocr_provider import TrOCRHandwrittenAdapter

_REGISTRY: dict[str, type[OCRProviderAdapter]] = {
    TesseractProvider.provider_code: TesseractProvider,
    EasyOCRProvider.provider_code: EasyOCRProvider,
    PaddleOCRProvider.provider_code: PaddleOCRProvider,
    AzureOCRProvider.provider_code: AzureOCRProvider,
    GoogleVisionProvider.provider_code: GoogleVisionProvider,
    AWSTextractProvider.provider_code: AWSTextractProvider,
    # Surya/docTR/TrOCR (isolated-runtime milestone) — each imported class
    # above only defines *how* to invoke the isolated venv; none of them
    # import surya/doctr/transformers at module load time (deferred to
    # first `extract()`/`health_check()` call), so registering them here
    # costs nothing when the corresponding isolated venv doesn't exist on
    # a given machine — see each adapter's own module docstring.
    DocTROCRAdapter.provider_code: DocTROCRAdapter,
    SuryaOCRAdapter.provider_code: SuryaOCRAdapter,
    TrOCRHandwrittenAdapter.provider_code: TrOCRHandwrittenAdapter,
}


def get_provider_adapter(code: str) -> OCRProviderAdapter:
    """Instantiate the adapter for `code`. Raises `KeyError` for an unknown
    code (should never happen if `code` came from a real `OCRProvider` row,
    since both are seeded from the same six names — see ADR-028)."""
    return _REGISTRY[code]()


def list_registered_codes() -> list[str]:
    return list(_REGISTRY.keys())
