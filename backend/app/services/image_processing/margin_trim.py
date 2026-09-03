"""Auto-detects and trims blank margins around the scanned content area —
unlike `crop.py`, no explicit bounding box is supplied by the caller."""

import cv2
import numpy as np

from app.services.image_processing.io_utils import to_grayscale

_DEFAULT_PADDING_PX = 10


def trim_margins(image: np.ndarray, *, padding: int = _DEFAULT_PADDING_PX) -> np.ndarray:
    gray = to_grayscale(image)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    coords = cv2.findNonZero(thresh)
    if coords is None:
        return image

    x, y, w, h = cv2.boundingRect(coords)
    img_height, img_width = image.shape[:2]
    left = max(0, x - padding)
    top = max(0, y - padding)
    right = min(img_width, x + w + padding)
    bottom = min(img_height, y + h + padding)
    return image[top:bottom, left:right]
