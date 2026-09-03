"""Fine-grained skew-angle detection (a few degrees, typical of a slightly
crooked scan) — distinct from `orientation.py`'s coarse 0/90/180/270
detection. Used by `deskew.py` to know how far to rotate."""

import cv2
import numpy as np

from app.services.image_processing.io_utils import to_grayscale


def detect_rotation_angle(image: np.ndarray) -> float:
    """Returns the estimated skew angle in degrees (positive = counter-clockwise).
    Minimum-area-rectangle approach over thresholded foreground pixels — cheap,
    dependency-free beyond OpenCV, and accurate for the common "scanned page
    laid slightly crooked" case this pipeline needs to correct."""
    gray = to_grayscale(image)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(thresh > 0))
    if coords.shape[0] < 10:
        return 0.0

    angle = cv2.minAreaRect(coords.astype(np.float32))[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    return round(float(angle), 2)
