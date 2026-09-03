"""Adaptive (local) thresholding — binarizes each region of the page
against its own local mean rather than one global threshold, so it copes
with uneven scan lighting (a shadow across half the page) that would make
a single global threshold cut too aggressively on one side. Distinct from
`contrast.py`'s CLAHE step, which brightens/darkens without ever fully
binarizing to black/white."""

import cv2
import numpy as np

from app.services.image_processing.io_utils import to_grayscale

_DEFAULT_BLOCK_SIZE = 35  # must be odd; larger = smoother/less locally-adaptive
_DEFAULT_C = 11  # constant subtracted from the local mean — higher = more aggressive


def adaptive_threshold(
    image: np.ndarray, *, block_size: int = _DEFAULT_BLOCK_SIZE, c: int = _DEFAULT_C
) -> np.ndarray:
    if block_size % 2 == 0:
        block_size += 1  # cv2 requires an odd block size
    gray = to_grayscale(image)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, c
    )
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
