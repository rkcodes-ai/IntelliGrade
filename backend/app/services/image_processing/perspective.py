"""Perspective correction — for a page photographed at an angle (phone
camera) rather than flat-bed scanned, straight edges in the real world
project as a non-rectangular quadrilateral in the image. Detects the
largest 4-point contour (assumed to be the page boundary against a
contrasting background) and warps it to a flat rectangle.

Deliberately conservative: if no clean quadrilateral is found (common for
a scan that's already flat, or a page that fills the whole frame with no
visible background), the image is returned unchanged rather than guessing
a bad warp — a wrong perspective transform is worse for OCR than none."""

import cv2
import numpy as np

from app.services.image_processing.io_utils import to_grayscale

_MIN_AREA_FRACTION = 0.2  # ignore candidate contours covering less than this share of the image


def correct_perspective(image: np.ndarray) -> np.ndarray:
    quad = _find_page_quadrilateral(image)
    if quad is None:
        return image
    return _warp_to_rectangle(image, quad)


def estimate_perspective_risk(image: np.ndarray) -> float:
    """0-100 heuristic used by `PageQualityAnalyzer` (Document Intelligence
    milestone) — reuses this module's own quadrilateral detector rather
    than a separate estimator. No quadrilateral found -> `0.0` (the same
    conservative "assume no distortion" stance `correct_perspective`
    itself takes, not a guess). When found, risk scales with how far the
    quad's four corner angles deviate from a perfect 90 degrees -- a
    flat/rectangular scan's corners are all ~90 degrees; a photographed,
    keystoned page's are not."""
    quad = _find_page_quadrilateral(image)
    if quad is None:
        return 0.0

    ordered = _order_corners(quad)
    max_deviation = 0.0
    for i in range(4):
        prev_point = ordered[i - 1]
        point = ordered[i]
        next_point = ordered[(i + 1) % 4]
        vector_a = prev_point - point
        vector_b = next_point - point
        norm_a = np.linalg.norm(vector_a)
        norm_b = np.linalg.norm(vector_b)
        if norm_a == 0 or norm_b == 0:
            continue
        cosine = np.clip(np.dot(vector_a, vector_b) / (norm_a * norm_b), -1.0, 1.0)
        angle_degrees = float(np.degrees(np.arccos(cosine)))
        max_deviation = max(max_deviation, abs(angle_degrees - 90.0))

    # A 45-degree-or-worse corner deviation is treated as maximally risky;
    # scaled linearly, clamped to [0, 100].
    return float(min(100.0, (max_deviation / 45.0) * 100.0))


def _find_page_quadrilateral(image: np.ndarray) -> np.ndarray | None:
    gray = to_grayscale(image)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    image_area = image.shape[0] * image.shape[1]
    best_quad: np.ndarray | None = None
    best_area = 0.0

    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) != 4:
            continue
        area = cv2.contourArea(approx)
        if area < _MIN_AREA_FRACTION * image_area or area <= best_area:
            continue
        best_area = area
        best_quad = approx.reshape(4, 2).astype(np.float32)

    return best_quad


def _order_corners(points: np.ndarray) -> np.ndarray:
    """Returns points ordered [top-left, top-right, bottom-right, bottom-left]."""
    total = points.sum(axis=1)
    diff = np.diff(points, axis=1).ravel()
    return np.array(
        [
            points[np.argmin(total)],  # top-left: smallest x+y
            points[np.argmin(diff)],  # top-right: smallest y-x
            points[np.argmax(total)],  # bottom-right: largest x+y
            points[np.argmax(diff)],  # bottom-left: largest y-x
        ],
        dtype=np.float32,
    )


def _warp_to_rectangle(image: np.ndarray, quad: np.ndarray) -> np.ndarray:
    ordered = _order_corners(quad)
    top_left, top_right, bottom_right, bottom_left = ordered

    width_top = np.linalg.norm(top_right - top_left)
    width_bottom = np.linalg.norm(bottom_right - bottom_left)
    height_left = np.linalg.norm(bottom_left - top_left)
    height_right = np.linalg.norm(bottom_right - top_right)

    target_width = max(int(width_top), int(width_bottom), 1)
    target_height = max(int(height_left), int(height_right), 1)

    destination = np.array(
        [
            [0, 0],
            [target_width - 1, 0],
            [target_width - 1, target_height - 1],
            [0, target_height - 1],
        ],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(ordered, destination)
    return cv2.warpPerspective(image, matrix, (target_width, target_height))
