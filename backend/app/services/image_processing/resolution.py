"""Normalizes page resolution so OCR always sees a consistent scale — a
photo taken at 4000px wide and a 300 DPI scan at 2480px wide should both
be resized to the same target before Tesseract sees them, since accuracy
degrades at both very low and unnecessarily high resolutions."""

import cv2
import numpy as np

_TARGET_LONG_EDGE_PX = 2480  # ~A4 at 300 DPI


def normalize_resolution(
    image: np.ndarray, *, target_long_edge: int = _TARGET_LONG_EDGE_PX
) -> np.ndarray:
    height, width = image.shape[:2]
    long_edge = max(height, width)
    if long_edge == 0:
        return image

    scale = target_long_edge / long_edge
    if abs(scale - 1.0) < 0.01:
        return image

    new_size = (round(width * scale), round(height * scale))
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    return cv2.resize(image, new_size, interpolation=interpolation)
