"""Auto brightness correction: shifts the image so its mean luminance sits
near a target value, without clipping the histogram (unlike a naive scalar
add, which would blow out already-bright regions of an unevenly-lit scan)."""

import cv2
import numpy as np

_TARGET_MEAN_LUMINANCE = 150.0


def correct_brightness(
    image: np.ndarray, *, target_mean: float = _TARGET_MEAN_LUMINANCE
) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    current_mean = float(gray.mean())
    if current_mean <= 0:
        return image

    gain = target_mean / current_mean
    gain = max(0.5, min(gain, 2.0))  # clamp to avoid over-correction on near-black/near-white pages
    return cv2.convertScaleAbs(image, alpha=gain, beta=0)
