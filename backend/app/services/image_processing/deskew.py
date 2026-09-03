"""Corrects the skew angle detected by `rotation.detect_rotation_angle`."""

import cv2
import numpy as np

from app.services.image_processing.rotation import detect_rotation_angle

_MIN_CORRECTABLE_ANGLE = 0.1  # skip the rotation entirely for near-zero skew


def deskew(image: np.ndarray, *, angle: float | None = None) -> np.ndarray:
    """`angle` can be pre-computed (e.g. once, then reused) or left `None`
    to detect it on this call."""
    resolved_angle = detect_rotation_angle(image) if angle is None else angle
    if abs(resolved_angle) < _MIN_CORRECTABLE_ANGLE:
        return image

    height, width = image.shape[:2]
    center = (width // 2, height // 2)
    matrix = cv2.getRotationMatrix2D(center, resolved_angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
