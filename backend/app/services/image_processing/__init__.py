"""
Modular image-preprocessing pipeline (Module 05, Stage 4).

Each step is a plain `(image: np.ndarray, **params) -> np.ndarray` (or, for
detectors, `(image) -> <value>`) transform — no step depends on any other
step's internals, so any one can be swapped, disabled, or reordered via
`OCRConfiguration.preprocessing_steps` without touching this package. See
ADR-033 and `docs/ocr-pipeline-guide.md`.
"""
