"""Unsharp masking — sharpens character edges softened by camera-phone
focus blur or scan resampling. Deliberately mild (a small `amount`) since
over-sharpening a page scan amplifies paper-texture/JPEG noise as much as
it does character edges, which hurts OCR more than it helps."""

import cv2
import numpy as np

_DEFAULT_AMOUNT = 0.5  # 0 = no effect, 1 = full-strength unsharp mask
_DEFAULT_BLUR_SIGMA = 2.0


def sharpen(
    image: np.ndarray, *, amount: float = _DEFAULT_AMOUNT, blur_sigma: float = _DEFAULT_BLUR_SIGMA
) -> np.ndarray:
    blurred = cv2.GaussianBlur(image, (0, 0), blur_sigma)
    sharpened = cv2.addWeighted(image, 1 + amount, blurred, -amount, 0)
    return sharpened
