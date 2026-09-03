"""Unit tests for `app.services.ocr.fusion` — the deterministic OCR
Fusion Engine (Six-Provider OCR milestone). Pure-function tests against
synthetic `OCRPageResult`s, no DB/Celery/provider dependency — the engine
itself has no I/O."""

from app.services.ocr.base import BoundingBox, OCRBlockResult, OCRLineResult, OCRPageResult
from app.services.ocr.fusion import (
    AGREEMENT_SIMILARITY_THRESHOLD,
    DEFAULT_PROVIDER_WEIGHTS,
    ProviderCandidate,
    fuse_page_candidates,
)


def _line(text: str, top: int, confidence: float) -> OCRLineResult:
    return OCRLineResult(
        text=text,
        bounding_box=BoundingBox(left=0, top=top, width=500, height=30),
        confidence=confidence,
        reading_order=0,
        words=[],
    )


def _page(lines: list[OCRLineResult]) -> OCRPageResult:
    block = OCRBlockResult(
        bounding_box=BoundingBox(0, 0, 500, 500), confidence=90.0, reading_order=0, lines=lines
    )
    return OCRPageResult(
        raw_text="\n".join(line.text for line in lines),
        average_confidence=90.0,
        language="eng",
        rotation_degrees=0.0,
        blocks=[block],
    )


def test_fusion_combines_agreeing_providers_with_weighted_confidence() -> None:
    tesseract = _page([_line("Photosynthesis converts light energy", 0, 90.0)])
    easyocr = _page([_line("Photosynthesis converts light energy", 2, 92.0)])

    result = fuse_page_candidates(
        [
            ProviderCandidate("tesseract", "success", tesseract),
            ProviderCandidate("easyocr", "success", easyocr),
        ]
    )

    assert result.raw_text == "Photosynthesis converts light energy"
    assert result.contributing_providers == ["easyocr", "tesseract"]
    assert result.disagreement_regions == []
    assert result.failed_providers == []
    assert 0.0 < result.average_confidence <= 100.0


def test_fusion_detects_and_records_genuine_disagreement() -> None:
    tesseract = _page([_line("into chemical energy", 0, 85.0)])
    easyocr = _page([_line("into totally different garbled text", 2, 60.0)])

    result = fuse_page_candidates(
        [
            ProviderCandidate("tesseract", "success", tesseract),
            ProviderCandidate("easyocr", "success", easyocr),
        ]
    )

    assert len(result.disagreement_regions) == 1
    region = result.disagreement_regions[0]
    assert region.similarity < AGREEMENT_SIMILARITY_THRESHOLD
    assert {c["provider_code"] for c in region.candidates} == {"tesseract", "easyocr"}
    # tesseract wins: 85 * 0.80 = 68.0 > easyocr's 60 * 0.82 = 49.2
    assert region.chosen_provider == "tesseract"
    assert result.raw_text == "into chemical energy"


def test_fusion_prefers_higher_weighted_confidence_provider() -> None:
    low_conf = _page([_line("wrong reading", 0, 50.0)])
    high_conf = _page([_line("correct reading", 2, 95.0)])

    result = fuse_page_candidates(
        [
            ProviderCandidate("tesseract", "success", low_conf),
            ProviderCandidate("google_vision", "success", high_conf),
        ]
    )

    assert result.raw_text == "correct reading"
    assert result.disagreement_regions[0].chosen_provider == "google_vision"


def test_fusion_tolerates_partial_provider_failure() -> None:
    tesseract = _page([_line("Photosynthesis converts light energy", 0, 90.0)])

    result = fuse_page_candidates(
        [
            ProviderCandidate("tesseract", "success", tesseract),
            ProviderCandidate(
                "paddleocr", "failed", None, error_message="dependency missing"
            ),
        ]
    )

    assert result.raw_text == "Photosynthesis converts light energy"
    assert result.contributing_providers == ["tesseract"]
    assert result.failed_providers == ["paddleocr"]


def test_fusion_returns_empty_result_when_every_provider_fails() -> None:
    result = fuse_page_candidates(
        [
            ProviderCandidate("tesseract", "failed", None, error_message="x"),
            ProviderCandidate("easyocr", "failed", None, error_message="y"),
        ]
    )

    assert result.raw_text == ""
    assert result.average_confidence == 0.0
    assert result.contributing_providers == []
    assert result.failed_providers == ["tesseract", "easyocr"]
    assert result.page_result is not None
    assert result.page_result.blocks == []


def test_fusion_single_successful_provider_passes_through_unchanged() -> None:
    tesseract = _page([_line("Only one provider ran", 0, 88.0)])

    result = fuse_page_candidates([ProviderCandidate("tesseract", "success", tesseract)])

    assert result.raw_text == "Only one provider ran"
    # Single-provider passthrough returns the page's own average_confidence
    # verbatim (90.0, set by the `_page()` fixture), not a per-line value —
    # no fusion computation happens when only one candidate succeeded.
    assert result.average_confidence == 90.0
    assert result.contributing_providers == ["tesseract"]
    assert result.disagreement_regions == []


def test_fusion_aligns_multiple_lines_by_vertical_position_not_by_order() -> None:
    """Providers that segment lines in a different order must still align
    correctly by geometry, not by list index."""
    tesseract = _page(
        [_line("first line", 0, 90.0), _line("second line", 40, 90.0)]
    )
    # EasyOCR-style: same two lines, same geometry, but constructed in a
    # different internal order to prove alignment is geometric.
    easyocr_lines = [_line("second line", 40, 92.0), _line("first line", 0, 92.0)]
    easyocr = _page(easyocr_lines)

    result = fuse_page_candidates(
        [
            ProviderCandidate("tesseract", "success", tesseract),
            ProviderCandidate("easyocr", "success", easyocr),
        ]
    )

    assert result.raw_text == "first line\nsecond line"
    assert result.disagreement_regions == []


def test_fusion_respects_explicit_weight_override() -> None:
    low_conf_but_high_weight = _page([_line("preferred text", 0, 60.0)])
    high_conf_but_low_weight = _page([_line("not preferred", 2, 95.0)])

    result = fuse_page_candidates(
        [
            ProviderCandidate(
                "tesseract", "success", low_conf_but_high_weight, weight=10.0
            ),
            ProviderCandidate(
                "google_vision", "success", high_conf_but_low_weight, weight=0.01
            ),
        ]
    )

    assert result.raw_text == "preferred text"


def test_default_provider_weights_cover_every_registered_local_and_cloud_provider() -> None:
    expected_codes = {
        "tesseract",
        "easyocr",
        "paddleocr",
        "doctr",
        "surya",
        "trocr_handwritten",
        "azure_ocr",
        "google_vision",
        "aws_textract",
    }
    assert expected_codes <= DEFAULT_PROVIDER_WEIGHTS.keys()
    assert all(0.0 < weight <= 1.0 for weight in DEFAULT_PROVIDER_WEIGHTS.values())
