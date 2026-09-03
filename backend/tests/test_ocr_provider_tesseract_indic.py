"""Real, unmocked Tesseract OCR verification for Indian-language
scripts (Step 4.2 milestone, Section 52). Uses the project-local
`.tessdata/` traineddata packs (downloaded from the official
tesseract-ocr/tessdata_fast repo, Apache-2.0) via `TESSERACT_TESSDATA_DIR`.

These are synthetic, PIL-rendered fixtures (Windows' `Nirmala.ttc` font)
— an honest proxy for printed text, not a claim of real scanned-exam
fidelity or handwriting-OCR capability (Section 53's printed-vs-
handwriting distinction). Recognition is real; exact-match is NOT
asserted (synthetic UI-font renders are not Tesseract's training
distribution) — these tests prove genuine, non-empty, appropriately-
scripted recognition occurred, matching this project's established
"never fabricate success" discipline.
"""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.config import get_settings
from app.services.document_intelligence.script_detection import detect_script
from app.services.ocr.providers.tesseract_provider import TesseractProvider

settings = get_settings()

_INDIC_FONT_PATH = "C:/Windows/Fonts/Nirmala.ttc"

_PRIORITY_A_SAMPLES: dict[str, tuple[str, str]] = {
    "tam": ("இயக்க முறைமையானது செயலாக்க அட்டவணையை நிர்வகிக்கிறது.", "TAMIL"),
    "hin": ("ऑपरेटिंग सिस्टम प्रोसेस शेड्यूलिंग को नियंत्रित करता है।", "DEVANAGARI"),
    "tel": ("ఆపరేటింగ్ సిస్టమ్ ప్రాసెస్ షెడ్యూలింగ్‌ను నిర్వహిస్తుంది.", "TELUGU"),
    "mal": ("ഓപ്പറേറ്റിംഗ് സിസ്റ്റം പ്രോസസ് ഷെഡ്യൂളിംഗ് കൈകാര്യം ചെയ്യുന്നു.", "MALAYALAM"),
    "kan": ("ಆಪರೇಟಿಂಗ್ ಸಿಸ್ಟಮ್ ಪ್ರಕ್ರಿಯೆ ವೇಳಾಪಟ್ಟಿಯನ್ನು ನಿರ್ವಹಿಸುತ್ತದೆ.", "KANNADA"),
}


def _render(text: str, tmp_path) -> str:
    img = Image.new("RGB", (1100, 100), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(_INDIC_FONT_PATH, 32)
    draw.text((10, 25), text, fill="black", font=font)
    path = str(tmp_path / "indic_sample.png")
    img.save(path)
    return path


_tessdata_available = bool(settings.TESSERACT_TESSDATA_DIR)


@pytest.mark.skipif(not _tessdata_available, reason="TESSERACT_TESSDATA_DIR not configured")
@pytest.mark.parametrize("code", list(_PRIORITY_A_SAMPLES))
def test_real_tesseract_recognizes_priority_a_language(code: str, tmp_path) -> None:
    text, expected_script = _PRIORITY_A_SAMPLES[code]
    image_path = _render(text, tmp_path)

    provider = TesseractProvider()
    result = provider.extract(image_path, language=code)

    assert result.raw_text.strip() != ""  # genuine, non-empty recognition occurred
    recognized_script = detect_script(result.raw_text).primary_script
    assert (
        recognized_script == expected_script
    )  # recognized text is genuinely in-script, not garbage/Latin


@pytest.mark.skipif(not _tessdata_available, reason="TESSERACT_TESSDATA_DIR not configured")
def test_real_tesseract_reports_installed_indic_language_packs() -> None:
    provider = TesseractProvider()
    languages = provider.supported_languages()
    for code in _PRIORITY_A_SAMPLES:
        assert code in languages


@pytest.mark.skipif(not _tessdata_available, reason="TESSERACT_TESSDATA_DIR not configured")
def test_real_tesseract_english_path_unaffected_by_tessdata_override(tmp_path) -> None:
    """Section 11: adding Indian-language packs must not change English
    OCR behavior."""
    img = Image.new("RGB", (400, 100), "white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 30), "Hello World", fill="black")
    path = str(tmp_path / "english_sample.png")
    img.save(path)

    provider = TesseractProvider()
    result = provider.extract(path, language="eng")
    assert "Hello" in result.raw_text or "World" in result.raw_text
