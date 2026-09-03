"""Unit tests for `app.services.document_intelligence.variant_selection`
— uses the real (already-verified) Tesseract adapter, no mocking, since
this module's whole purpose is comparing genuine OCR evidence."""

import cv2
import numpy as np

from app.services.document_intelligence.variant_selection import select_best_variant


def _text_image(height: int = 200, width: int = 700) -> np.ndarray:
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(image, "Real evidence based selection test", (20, 100), font, 1.0, (0, 0, 0), 2)
    return image


def test_no_operations_applied_trivially_selects_original_without_ocr_probe() -> None:
    image = _text_image()
    result = select_best_variant(image, image, operations_applied=[])
    assert result.selected == "original"
    assert result.original_confidence == 0.0  # no probe was run
    assert "no enhancement operations" in result.reason


def test_genuinely_improved_variant_is_selected() -> None:
    """A real deskew fixes real, significant skew -- the enhanced variant
    should win on genuine OCR confidence. Uses a large (18 degree) skew so
    the effect is unambiguous — Tesseract tolerates small skew angles well
    enough that a marginal skew doesn't reliably move confidence."""
    image = _text_image()
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width // 2, height // 2), 18.0, 1.0)
    skewed = cv2.warpAffine(image, matrix, (width, height), borderValue=(255, 255, 255))
    # "enhanced" here is literally the deskewed-back version of the skewed original.
    unskew_matrix = cv2.getRotationMatrix2D((width // 2, height // 2), -18.0, 1.0)
    deskewed = cv2.warpAffine(skewed, unskew_matrix, (width, height), borderValue=(255, 255, 255))

    result = select_best_variant(skewed, deskewed, operations_applied=["deskew"])
    assert result.selected == "enhanced"
    assert result.enhanced_confidence > result.original_confidence


def test_variant_that_destroys_text_is_rejected_even_if_it_would_score_higher() -> None:
    """Safety net: an enhanced variant with near-zero recovered text must
    never be selected, regardless of confidence."""
    image = _text_image()
    blank = np.full(image.shape, 255, dtype=np.uint8)  # simulates a destructive over-threshold wipe

    result = select_best_variant(image, blank, operations_applied=["adaptive_threshold"])
    assert result.selected == "original"
    assert "lost significant text" in result.reason


def test_marginal_confidence_difference_does_not_flip_selection() -> None:
    image = _text_image()
    # A pixel-identical "enhanced" copy should never be preferred over the
    # original purely due to OCR nondeterminism noise.
    identical_copy = image.copy()
    result = select_best_variant(image, identical_copy, operations_applied=["contrast"])
    assert result.selected == "original"
