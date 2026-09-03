"""Splits a single scanned image that contains two physical pages side by
side (a common artifact of book/booklet scanning) into two separate page
images. Detects the vertical gutter as the column with the lowest ink
density near the horizontal center — a light-weight heuristic, not a
general layout analyzer. Returns the original single image unsplit if no
clear gutter is found (most answer-script scans are already single-page)."""

import numpy as np

from app.services.image_processing.io_utils import to_grayscale

_CENTER_SEARCH_FRACTION = 0.15  # search the middle 30% of the width for the gutter
_GUTTER_WHITENESS_THRESHOLD = 250  # near-pure-white column = likely gutter


def split_double_page(image: np.ndarray) -> list[np.ndarray]:
    gray = to_grayscale(image)
    height, width = gray.shape
    search_start = int(width * (0.5 - _CENTER_SEARCH_FRACTION))
    search_end = int(width * (0.5 + _CENTER_SEARCH_FRACTION))
    if search_end <= search_start:
        return [image]

    column_means = gray[:, search_start:search_end].mean(axis=0)
    gutter_offset = int(np.argmax(column_means))
    if column_means[gutter_offset] < _GUTTER_WHITENESS_THRESHOLD:
        return [image]  # no sufficiently clean gutter found -- treat as single page

    gutter_x = search_start + gutter_offset
    left_page = image[:, :gutter_x]
    right_page = image[:, gutter_x:]
    return [left_page, right_page]
