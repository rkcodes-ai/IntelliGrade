"""Contrast enhancement via CLAHE (Contrast Limited Adaptive Histogram
Equalization) — chosen over plain global histogram equalization because it
avoids over-amplifying noise in the blank margins of a scanned page."""

import cv2
import numpy as np


def enhance_contrast(
    image: np.ndarray, *, clip_limit: float = 2.0, tile_grid_size: int = 8
) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_grid_size, tile_grid_size))
    enhanced_l = clahe.apply(l_channel)
    merged = cv2.merge((enhanced_l, a_channel, b_channel))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
