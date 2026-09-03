"""
Original-vs-Enhanced variant selection (Document Intelligence milestone,
Section 12: "Never assume enhanced = better"). Runs a fast, always-available
OCR pass (Tesseract — already the default provider, no model download,
CPU-only, milliseconds per page) against both the original and the
enhanced page image and picks whichever genuinely produces better OCR
evidence, rather than trusting the enhancement pipeline blindly.

Deliberately NOT the full six-provider ensemble for this decision — that
would multiply this milestone's per-page cost by 6x just to pick which
*input* to eventually feed the real ensemble, which is itself already
expensive. Tesseract's confidence/character-count numbers are a real,
fast, honest proxy signal for "did this transformation help or hurt",
not a claim that Tesseract is used for final recognition.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from app.services.image_processing.io_utils import encode_image_to_bytes
from app.services.ocr.providers.tesseract_provider import TesseractProvider

SelectedVariant = Literal["original", "enhanced"]

# The enhanced variant must beat the original by more than this margin to
# be selected — a tiny, statistically-insignificant confidence delta
# should not flip the decision (avoids selection noise on pages where
# enhancement genuinely made no real difference).
_MIN_CONFIDENCE_ADVANTAGE = 1.5


@dataclass(frozen=True)
class VariantSelectionResult:
    selected: SelectedVariant
    reason: str
    original_confidence: float
    enhanced_confidence: float
    original_character_count: int
    enhanced_character_count: int


def _ocr_probe(image: np.ndarray, *, language: str) -> tuple[float, int]:
    provider = TesseractProvider()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(encode_image_to_bytes(image))
        tmp_path = tmp.name
    try:
        result = provider.extract(tmp_path, language=language)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return result.average_confidence, len(result.raw_text.strip())


def select_best_variant(
    original: np.ndarray,
    enhanced: np.ndarray,
    *,
    operations_applied: list[str],
    language: str = "eng",
) -> VariantSelectionResult:
    """No enhancement operations were applied -> trivially "original"
    without spending an extra OCR probe (the two images are pixel-
    identical in that case anyway)."""
    if not operations_applied:
        return VariantSelectionResult(
            selected="original",
            reason="no enhancement operations were applied",
            original_confidence=0.0,
            enhanced_confidence=0.0,
            original_character_count=0,
            enhanced_character_count=0,
        )

    original_confidence, original_chars = _ocr_probe(original, language=language)
    enhanced_confidence, enhanced_chars = _ocr_probe(enhanced, language=language)

    # A variant that lost the majority of its recognizable text relative
    # to the other is disqualified outright regardless of confidence —
    # confidence alone can't be trusted if enhancement destroyed most of
    # the content (e.g. over-aggressive thresholding erasing faint ink).
    if enhanced_chars < original_chars * 0.5 and original_chars > 0:
        return VariantSelectionResult(
            selected="original",
            reason=(
                f"enhanced variant lost significant text "
                f"({enhanced_chars} vs {original_chars} original chars)"
            ),
            original_confidence=original_confidence,
            enhanced_confidence=enhanced_confidence,
            original_character_count=original_chars,
            enhanced_character_count=enhanced_chars,
        )

    if enhanced_confidence >= original_confidence + _MIN_CONFIDENCE_ADVANTAGE:
        return VariantSelectionResult(
            selected="enhanced",
            reason=(
                f"enhanced OCR confidence {enhanced_confidence:.2f} beat original "
                f"{original_confidence:.2f} by >= {_MIN_CONFIDENCE_ADVANTAGE}"
            ),
            original_confidence=original_confidence,
            enhanced_confidence=enhanced_confidence,
            original_character_count=original_chars,
            enhanced_character_count=enhanced_chars,
        )

    return VariantSelectionResult(
        selected="original",
        reason=(
            f"enhanced OCR confidence {enhanced_confidence:.2f} did not beat original "
            f"{original_confidence:.2f} by a meaningful margin"
        ),
        original_confidence=original_confidence,
        enhanced_confidence=enhanced_confidence,
        original_character_count=original_chars,
        enhanced_character_count=enhanced_chars,
    )
