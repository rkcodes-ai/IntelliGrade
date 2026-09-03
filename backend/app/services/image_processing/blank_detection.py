"""Detects near-blank pages (e.g. an intentionally left-blank sheet in a
scanned answer booklet) so the pipeline can skip OCR on them entirely —
saves processing time and avoids polluting `OCRResult` with noise."""

import cv2
import numpy as np

from app.services.image_processing.io_utils import to_grayscale

_DEFAULT_INK_RATIO_THRESHOLD = 0.005  # fewer than 0.5% dark pixels = blank


def is_blank_page(
    image: np.ndarray, *, ink_ratio_threshold: float = _DEFAULT_INK_RATIO_THRESHOLD
) -> bool:
    gray = to_grayscale(image)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    ink_pixels = int(cv2.countNonZero(thresh))
    total_pixels = thresh.shape[0] * thresh.shape[1]
    if total_pixels == 0:
        return True
    return bool((ink_pixels / total_pixels) < ink_ratio_threshold)
