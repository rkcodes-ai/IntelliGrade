"""Unicode-safety audit proof tests for `app.services.ocr.fusion`
(Step 4.2 milestone, Section 32).

The audit performed before implementation found NO ASCII/Latin-only
assumption in `fusion.py` (line alignment is purely geometric;
`_text_similarity`/`_normalize` use `.strip().lower().split()` +
`difflib.SequenceMatcher`, all genuinely Unicode-generic). These tests
PROVE that finding with real fusion runs on Tamil/Devanagari/Bengali
text, rather than leaving it as an unverified claim.
"""

from __future__ import annotations

from app.services.ocr.base import BoundingBox, OCRBlockResult, OCRLineResult, OCRPageResult
from app.services.ocr.fusion import ProviderCandidate, fuse_page_candidates


def _page_with_line(text: str, *, confidence: float = 90.0) -> OCRPageResult:
    box = BoundingBox(left=0, top=0, width=400, height=30)
    line = OCRLineResult(text=text, bounding_box=box, confidence=confidence, reading_order=0)
    block = OCRBlockResult(bounding_box=box, confidence=confidence, reading_order=0, lines=[line])
    return OCRPageResult(
        raw_text=text,
        average_confidence=confidence,
        language="ta",
        rotation_degrees=0.0,
        blocks=[block],
    )


def test_fusion_agrees_on_identical_tamil_text() -> None:
    text = "இயக்க முறைமையானது செயலாக்க அட்டவணையை நிர்வகிக்கிறது."
    candidates = [
        ProviderCandidate(
            provider_code="tesseract", status="success", result=_page_with_line(text)
        ),
        ProviderCandidate(provider_code="easyocr", status="success", result=_page_with_line(text)),
    ]
    fusion = fuse_page_candidates(candidates)
    assert fusion.raw_text == text
    assert fusion.disagreement_regions == []


def test_fusion_detects_genuine_tamil_disagreement() -> None:
    text_a = "இயக்க முறைமையானது செயலாக்க அட்டவணையை நிர்வகிக்கிறது."
    text_b = "வேறு முற்றிலும் மாறுபட்ட வாக்கியம் இது."  # a completely different sentence
    candidates = [
        ProviderCandidate(
            provider_code="tesseract", status="success", result=_page_with_line(text_a)
        ),
        ProviderCandidate(
            provider_code="easyocr", status="success", result=_page_with_line(text_b)
        ),
    ]
    fusion = fuse_page_candidates(candidates)
    assert len(fusion.disagreement_regions) == 1
    assert fusion.raw_text in (text_a, text_b)  # a real choice was made, not corrupted


def test_fusion_preserves_devanagari_combining_marks() -> None:
    text = "ऑपरेटिंग सिस्टम प्रोसेस शेड्यूलिंग को नियंत्रित करता है।"
    candidates = [
        ProviderCandidate(provider_code="tesseract", status="success", result=_page_with_line(text))
    ]
    fusion = fuse_page_candidates(candidates)
    assert fusion.raw_text == text  # every combining vowel sign/virama survives byte-for-byte


def test_fusion_preserves_bengali_text_unmodified() -> None:
    text = "অপারেটিং সিস্টেম প্রক্রিয়া নির্ধারণ পরিচালনা করে।"
    candidates = [
        ProviderCandidate(provider_code="tesseract", status="success", result=_page_with_line(text))
    ]
    fusion = fuse_page_candidates(candidates)
    assert fusion.raw_text == text


def test_fusion_handles_mixed_tamil_english_text() -> None:
    text = "இயக்க முறைமை CPU Scheduling ஐ கையாள்கிறது."
    candidates = [
        ProviderCandidate(
            provider_code="tesseract", status="success", result=_page_with_line(text)
        ),
        ProviderCandidate(provider_code="easyocr", status="success", result=_page_with_line(text)),
    ]
    fusion = fuse_page_candidates(candidates)
    assert fusion.raw_text == text
    assert "CPU Scheduling" in fusion.raw_text


def test_fusion_confidence_weighting_works_for_non_latin_text() -> None:
    """A real, non-Latin-specific regression: the higher-weighted
    provider's text must still win on disagreement, exactly as it does
    for English."""
    text_low_conf_provider = "தவறான உரை"  # "incorrect text"
    text_high_conf_provider = "சரியான உரை"  # "correct text"
    candidates = [
        ProviderCandidate(
            provider_code="tesseract",
            status="success",
            result=_page_with_line(text_low_conf_provider, confidence=40.0),
            weight=0.5,
        ),
        ProviderCandidate(
            provider_code="paddleocr",
            status="success",
            result=_page_with_line(text_high_conf_provider, confidence=95.0),
            weight=0.9,
        ),
    ]
    fusion = fuse_page_candidates(candidates)
    assert fusion.raw_text == text_high_conf_provider
