"""Crop to an explicit bounding box (pixel coordinates, top-left origin —
same convention as `app.services.ocr.base.BoundingBox`). For automatic
content-area detection instead of an explicit box, see `margin_trim.py`."""

import numpy as np


def crop_to_bbox(image: np.ndarray, *, left: int, top: int, width: int, height: int) -> np.ndarray:
    img_height, img_width = image.shape[:2]
    left = max(0, left)
    top = max(0, top)
    right = min(img_width, left + width)
    bottom = min(img_height, top + height)
    return image[top:bottom, left:right]
