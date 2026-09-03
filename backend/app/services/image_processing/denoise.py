"""Denoise / noise removal — the prompt lists these as two bullets but
they're the same operation; consolidated into one step (same "don't split
one capability into two near-identical entries" reasoning as ADR-029)."""

import cv2
import numpy as np


def denoise(image: np.ndarray, *, strength: int = 10) -> np.ndarray:
    return cv2.fastNlMeansDenoisingColored(image, None, strength, strength, 7, 21)
