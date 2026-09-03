"""Unit tests for the OCR provider adapter layer (Module 12): the real
Tesseract adapter, the real-but-environment-dependent EasyOCR/PaddleOCR
adapters, the three real-but-credential-gated cloud adapters, and the
code->adapter registry.

All six providers are real, complete implementations now (`is_implemented
= True` everywhere) — none of them are the pre-Module-12
`OCRProviderNotImplementedError` stubs any more. What still varies per
provider is whether *this test environment* can actually exercise it:
Tesseract always can (it's installed); EasyOCR depends on a local package
being importable; **PaddleOCR now runs through the isolated `.venv-
paddleocr` runtime bridge** (Surya/docTR/TrOCR milestone, Section 16) —
on a machine without that venv it raises `OCRIsolatedRuntimeMissingError`
instead of `OCRDependencyMissingError`, so both are treated as the same
"not available in this environment" outcome below; the three cloud
providers depend on real credentials this suite deliberately never
fabricates. Each case is asserted for the failure mode it should actually
produce, never a bare "it raised something"."""

import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.core.config import get_settings
from app.services.image_processing.io_utils import save_image
from app.services.ocr.exceptions import (
    OCRDependencyMissingError,
    OCRIsolatedRuntimeMissingError,
    OCRProviderConfigurationError,
)
from app.services.ocr.providers.aws_textract_provider import AWSTextractProvider
from app.services.ocr.providers.azure_provider import AzureOCRProvider
from app.services.ocr.providers.easyocr_provider import EasyOCRProvider
from app.services.ocr.providers.google_vision_provider import GoogleVisionProvider
from app.services.ocr.providers.paddleocr_provider import PaddleOCRProvider
from app.services.ocr.providers.tesseract_provider import TesseractProvider
from app.services.ocr.registry import get_provider_adapter, list_registered_codes

ALL_PROVIDER_CLASSES = [
    TesseractProvider,
    EasyOCRProvider,
    PaddleOCRProvider,
    AzureOCRProvider,
    GoogleVisionProvider,
    AWSTextractProvider,
]


def _text_image_path(tmp_path) -> str:
    image = Image.new("RGB", (400, 200), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 40), "HELLO WORLD", fill="black")
    draw.text((20, 90), "SECOND LINE HERE", fill="black")
    path = str(tmp_path / "sample.png")
    save_image(np.array(image), path)
    return path


def test_tesseract_provider_extracts_text_with_hierarchy(tmp_path) -> None:
    provider = TesseractProvider()
    result = provider.extract(_text_image_path(tmp_path), language="eng")

    assert "HELLO" in result.raw_text.upper()
    assert result.language == "eng"
    assert isinstance(result.rotation_degrees, float)
    assert 0.0 <= result.average_confidence <= 100.0
    assert len(result.blocks) >= 1

    block = result.blocks[0]
    assert block.bounding_box.width > 0
    assert block.bounding_box.height > 0
    assert len(block.lines) >= 1
    assert block.text != ""

    line = block.lines[0]
    assert len(line.words) >= 1
    assert line.words[0].bounding_box.width > 0


def test_tesseract_provider_handles_blank_image(tmp_path) -> None:
    blank = np.full((100, 200, 3), 255, dtype=np.uint8)
    path = str(tmp_path / "blank.png")
    save_image(blank, path)

    provider = TesseractProvider()
    result = provider.extract(path, language="eng")

    assert result.raw_text == ""
    assert result.blocks == []
    assert result.average_confidence == 0.0


def test_tesseract_provider_reads_an_extreme_aspect_ratio_single_line_strip(tmp_path) -> None:
    """Regression test (Six-Provider OCR milestone, Phase 14): Tesseract's
    own default page-segmentation mode (PSM 3, "fully automatic") can find
    *zero* text regions on an extreme-aspect-ratio strip -- exactly what
    this project's `trim_margins` preprocessing step produces for a
    single-line page. Confirmed via a real multi-page-PDF end-to-end run
    where one of two nearly-identical single-line pages OCR'd to an empty
    string under PSM 3 while the other didn't. `TesseractProvider.extract()`
    now detects an extreme aspect ratio and substitutes PSM 6 automatically
    (see `_resolve_effective_psm`) -- build a real ~14:1 strip here (the
    exact shape that triggered the original failure) and confirm text is
    recognized reliably, not "most of the time"."""
    image = Image.new("RGB", (2480, 175), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 50), "PAGE TWO CONTENT HERE", fill="black")
    path = str(tmp_path / "extreme_strip.png")
    save_image(np.array(image), path)

    provider = TesseractProvider()
    result = provider.extract(path, language="eng")

    assert "PAGE" in result.raw_text.upper()
    assert "CONTENT" in result.raw_text.upper()


def test_resolve_effective_psm_leaves_normal_pages_on_tesseract_default(tmp_path) -> None:
    from app.services.ocr.providers.tesseract_provider import _resolve_effective_psm

    normal_page = Image.new("RGB", (800, 1000), color="white")
    path = str(tmp_path / "normal_page.png")
    save_image(np.array(normal_page), path)

    assert _resolve_effective_psm(path, None) is None


def test_resolve_effective_psm_honors_explicit_configuration(tmp_path) -> None:
    from app.services.ocr.providers.tesseract_provider import _resolve_effective_psm

    strip = Image.new("RGB", (2480, 175), color="white")
    path = str(tmp_path / "strip.png")
    save_image(np.array(strip), path)

    # Explicit configuration always wins, even on an extreme-aspect-ratio image.
    assert _resolve_effective_psm(path, 11) == 11


@pytest.mark.parametrize("provider_cls", ALL_PROVIDER_CLASSES)
def test_all_six_providers_are_marked_implemented(provider_cls: type) -> None:
    """Module 12: every provider is a real implementation now, not a stub —
    what differs is deployment readiness (installed packages, credentials),
    which `health_check()`/`is_implemented` report separately (see below)."""
    assert provider_cls().is_implemented is True


#: Settings a developer's local `.env` may legitimately have populated
#: with real credentials (e.g. to verify a cloud provider by hand) — the
#: two tests below must force these back to "absent" regardless of the
#: ambient environment, since their entire premise is "no credentials".
_CLOUD_CREDENTIAL_SETTINGS = (
    "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT",
    "AZURE_DOCUMENT_INTELLIGENCE_API_KEY",
    "GOOGLE_VISION_CREDENTIALS_PATH",
    "AWS_TEXTRACT_REGION",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
)


def _clear_cloud_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    for name in _CLOUD_CREDENTIAL_SETTINGS:
        monkeypatch.setattr(settings, name, None)


@pytest.mark.parametrize(
    "provider_cls", [AzureOCRProvider, GoogleVisionProvider, AWSTextractProvider]
)
def test_cloud_providers_raise_configuration_error_without_credentials(
    provider_cls: type, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real SDK-based code exists for all three (see each provider's own
    module) and none can be exercised without real cloud credentials, which
    this test suite deliberately never fabricates — calling `extract()`
    unconfigured must fail with the specific `OCRProviderConfigurationError`,
    distinct from "not implemented". Cloud credentials are force-cleared
    (see `_clear_cloud_credentials`) so this holds even on a machine whose
    `.env` has real credentials configured for manual verification."""
    _clear_cloud_credentials(monkeypatch)
    provider = provider_cls()
    with pytest.raises(OCRProviderConfigurationError):
        provider.extract("irrelevant-path.png")


@pytest.mark.parametrize(
    "provider_cls", [AzureOCRProvider, GoogleVisionProvider, AWSTextractProvider]
)
def test_cloud_providers_health_check_reports_unconfigured_honestly(
    provider_cls: type, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without real credentials, health_check() must say so plainly
    (`configured=False`, `ready=False`) rather than guessing or crashing."""
    _clear_cloud_credentials(monkeypatch)
    result = provider_cls().health_check()
    assert result.installed is True  # the SDK package itself is installed in this test env
    assert result.configured is False
    assert result.ready is False
    assert result.detail  # a human-readable reason must be present


@pytest.mark.parametrize("provider_cls", [EasyOCRProvider, PaddleOCRProvider])
def test_local_ml_providers_are_marked_implemented(provider_cls: type) -> None:
    """EasyOCR/PaddleOCR are real, complete implementations (Module 12) —
    unlike the cloud providers, no credentials are needed, only a local
    package install. `is_implemented` is `True` regardless of whether the
    package happens to be importable in *this* environment (see the next
    test for that distinction)."""
    assert provider_cls().is_implemented is True


@pytest.mark.parametrize("provider_cls", [EasyOCRProvider, PaddleOCRProvider])
def test_local_ml_providers_extract_or_fail_cleanly(provider_cls: type, tmp_path) -> None:
    """Environment-dependent: if the provider is genuinely available here,
    `extract()` must return a real, structurally valid result exactly like
    Tesseract's. If it isn't — EasyOCR: missing package, or a native
    dependency blocked by an OS code-integrity policy; PaddleOCR: the
    isolated `.venv-paddleocr` runtime (see `providers/paddleocr_provider.py`)
    doesn't exist on this machine — it must fail with the specific
    `OCRDependencyMissingError`/`OCRIsolatedRuntimeMissingError`, never an
    uncaught exception of some other type."""
    provider = provider_cls()
    try:
        result = provider.extract(_text_image_path(tmp_path), language="eng")
    except (OCRDependencyMissingError, OCRIsolatedRuntimeMissingError):
        return
    assert isinstance(result.raw_text, str)
    assert result.language == "eng"
    assert 0.0 <= result.average_confidence <= 100.0


@pytest.mark.parametrize("provider_cls", [EasyOCRProvider, PaddleOCRProvider])
def test_local_ml_providers_health_check_never_crashes(provider_cls: type) -> None:
    """The health check must always return a structured result — including
    when the underlying package/native dependency can't load — never raise,
    since the OCR Administration page calls this for every provider on
    every page load regardless of what's actually installed."""
    result = provider_cls().health_check()
    assert result.provider_code == provider_cls.provider_code
    assert isinstance(result.installed, bool)
    assert isinstance(result.ready, bool)


def test_registry_lists_all_nine_provider_codes() -> None:
    """Six local + three cloud, after the Surya/docTR/TrOCR
    isolated-runtime milestone added three new local provider codes to
    the original six."""
    codes = list_registered_codes()
    assert set(codes) == {
        "tesseract",
        "easyocr",
        "paddleocr",
        "surya",
        "doctr",
        "trocr_handwritten",
        "azure_ocr",
        "google_vision",
        "aws_textract",
    }


def test_registry_returns_tesseract_adapter_instance() -> None:
    adapter = get_provider_adapter("tesseract")
    assert isinstance(adapter, TesseractProvider)


def test_registry_raises_key_error_for_unknown_code() -> None:
    with pytest.raises(KeyError):
        get_provider_adapter("not-a-real-provider")
