"""Format-agnostic image load/save. Uses Pillow (broadest format support —
PNG/JPG/TIFF/BMP/WEBP all decode reliably without extra system codecs,
unlike raw `cv2.imread` on some platforms) and converts to/from the BGR
`np.ndarray` shape every other `image_processing` step expects (OpenCV's
native channel order)."""

import io

import numpy as np
from PIL import Image


def load_image(path: str) -> np.ndarray:
    with Image.open(path) as img:
        rgb = img.convert("RGB")
        return np.array(rgb)[:, :, ::-1].copy()  # RGB -> BGR


def save_image(image: np.ndarray, path: str) -> None:
    rgb = image[:, :, ::-1]  # BGR -> RGB
    Image.fromarray(rgb).save(path)


def load_image_from_bytes(data: bytes) -> np.ndarray:
    """Same as `load_image`, but reads from in-memory bytes — what the
    pipeline actually has after downloading a page from object storage,
    rather than a local file path."""
    with Image.open(io.BytesIO(data)) as img:
        rgb = img.convert("RGB")
        return np.array(rgb)[:, :, ::-1].copy()  # RGB -> BGR


def encode_image_to_bytes(image: np.ndarray, *, image_format: str = "PNG") -> bytes:
    rgb = image[:, :, ::-1]  # BGR -> RGB
    buffer = io.BytesIO()
    Image.fromarray(rgb).save(buffer, format=image_format)
    return buffer.getvalue()


def to_grayscale(image: np.ndarray) -> np.ndarray:
    import cv2

    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
