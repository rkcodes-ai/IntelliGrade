"""Rasterizes a PDF's pages into images (PyMuPDF/`fitz` — bundles MuPDF, no
system `poppler` dependency required, unlike `pdf2image`). This is upload
plumbing that runs before any of the 12 preprocessing steps can apply
(they all operate on a single page image, not a multi-page PDF) — see
ADR-033's docstring note distinguishing this from the numbered steps."""

import numpy as np
import pymupdf

_DEFAULT_DPI = 300


def extract_page_count(pdf_bytes: bytes) -> int:
    # PyMuPDF ships a `py.typed` marker but its compiled/generated
    # `Document`/`Matrix` constructors and attributes aren't meaningfully
    # annotated -- mypy sees them as untyped, hence the targeted ignores
    # below (an `ignore_missing_imports` module override wouldn't apply
    # here, since the import itself isn't what's missing).
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:  # type: ignore[no-untyped-call]
        page_count: int = doc.page_count
        return page_count


def extract_pages_as_images(pdf_bytes: bytes, *, dpi: int = _DEFAULT_DPI) -> list[np.ndarray]:
    zoom = dpi / 72  # PDF's native unit is 72 DPI
    matrix = pymupdf.Matrix(zoom, zoom)  # type: ignore[no-untyped-call]
    images: list[np.ndarray] = []

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:  # type: ignore[no-untyped-call]
        for page in doc:
            pix = page.get_pixmap(matrix=matrix, colorspace=pymupdf.csRGB)
            array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            images.append(array[:, :, ::-1].copy())  # RGB -> BGR, matches io_utils' convention

    return images
