"""Background cleaning — estimates the page's uneven background
illumination (a large-kernel morphological "open", which erases anything
smaller than the kernel — i.e. the text — leaving just the background
gradient) and divides it out, flattening shadows/gradients without fully
binarizing the page the way `adaptive_threshold.py` does. Distinct from
`margin_trim.py`, which crops blank borders rather than correcting
illumination within the content area."""

import cv2
import numpy as np

DEFAULT_BACKGROUND_KERNEL_SIZE = 25  # must exceed stroke width so text is erased, not background


def clean_background(
    image: np.ndarray, *, kernel_size: int = DEFAULT_BACKGROUND_KERNEL_SIZE
) -> np.ndarray:
    gray: np.ndarray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    background = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel)

    # Avoid a divide-by-zero on fully-black background estimate pixels.
    background_safe = np.where(background == 0, 1, background).astype(np.float32)
    normalized = (gray.astype(np.float32) / background_safe) * 255.0
    cleaned: np.ndarray = np.clip(normalized, 0, 255).astype(np.uint8)
    if image.ndim != 3:
        return cleaned

    result: np.ndarray = cv2.cvtColor(cleaned, cv2.COLOR_GRAY2BGR)
    return result
