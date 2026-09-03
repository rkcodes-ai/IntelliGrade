"""Coarse page-orientation detection (0/90/180/270 degrees) — distinct from
`rotation.py`'s fine-grained skew angle. Heuristic: text laid out
horizontally produces a strongly periodic row-sum profile (alternating
light text-line bands and dark inter-line gaps); the correct orientation
is the one with the highest row-sum variance. This is a best-effort
signal, not a trained classifier — an engine-assisted approach (e.g.
Tesseract's OSD, already used for skew in `ocr.providers.tesseract_
provider`) would be more accurate but would couple image preprocessing to
one specific OCR engine, which ADR-033 deliberately avoids.

**Known, deliberate limitation**: row-sum *variance* is mathematically
identical whether a row-sum profile is read top-to-bottom or bottom-to-
top — rotating an image 180 degrees exactly reverses the order of its row
sums without changing their distribution, so variance alone can never
distinguish 0 degrees from 180 (or, by the same argument, 90 from 270).
Comparing all four candidates naively (as an earlier version of this
function did) makes that 0-vs-180 choice come down to floating-point
noise from `cv2.rotate()`'s interpolation — confirmed to actually flip a
correctly-oriented, realistic multi-line page 180 degrees during the OCR
Six-Provider milestone's real-infrastructure verification (a live
Celery-worker end-to-end run genuinely mangled otherwise-perfect Tesseract
output this way). This function therefore only uses variance to choose
between the *upright* pair (0/180) and the *sideways* pair (90/270) —
each pair's own internal variance total is identical by the same
invariant, so there is nothing to lose by always resolving to the first
member of whichever pair wins (0 for upright, 90 for sideways). Genuinely
upside-down scans are rare for this application's document types (typed
question papers, printed model answers, handwritten answer scripts) next
to sideways phone-camera captures, so defaulting to "upright, not
inverted" is the safer failure mode — never flipping content that was
already correct, at the cost of not fixing the rarer true 180 case."""

import cv2
import numpy as np

from app.services.image_processing.io_utils import to_grayscale

_CANDIDATE_ROTATIONS = (0, 90, 180, 270)


def detect_orientation(image: np.ndarray) -> int:
    gray = to_grayscale(image)

    def variance_at(rotation: int) -> float:
        rotated = _rotate_90_multiple(gray, rotation)
        row_sums = rotated.astype(np.float64).sum(axis=1)
        return float(row_sums.var())

    # See module docstring: 0 vs 180 (and 90 vs 270) are mathematically
    # indistinguishable by row-sum variance, so only the upright-vs-sideways
    # choice is meaningful here.
    upright_variance = variance_at(0)
    sideways_variance = variance_at(90)
    return 0 if upright_variance >= sideways_variance else 90


def correct_orientation(image: np.ndarray, *, rotation: int | None = None) -> np.ndarray:
    resolved = detect_orientation(image) if rotation is None else rotation
    return _rotate_90_multiple(image, resolved)


def _rotate_90_multiple(image: np.ndarray, degrees: int) -> np.ndarray:
    degrees = degrees % 360
    if degrees == 0:
        return image
    if degrees == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    if degrees == 180:
        return cv2.rotate(image, cv2.ROTATE_180)
    if degrees == 270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    raise ValueError(f"Orientation must be one of {_CANDIDATE_ROTATIONS}, got {degrees}")
