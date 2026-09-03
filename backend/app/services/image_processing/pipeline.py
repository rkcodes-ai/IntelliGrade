"""
Composes the individual preprocessing steps into one configurable pass —
the piece `OCRConfiguration.preprocessing_steps` (a plain ordered list of
step names) actually drives. Orientation/deskew are detection+correction
in one step here (the pipeline always wants both); page-splitting and
blank-detection are handled by the caller (`app.tasks.ocr_tasks`) before
this pipeline runs, since they change the *number* of pages rather than
transforming one page image.
"""

from collections.abc import Callable

import numpy as np

from app.services.image_processing.adaptive_threshold import adaptive_threshold
from app.services.image_processing.background_clean import clean_background
from app.services.image_processing.brightness import correct_brightness
from app.services.image_processing.contrast import enhance_contrast
from app.services.image_processing.denoise import denoise
from app.services.image_processing.deskew import deskew
from app.services.image_processing.margin_trim import trim_margins
from app.services.image_processing.orientation import correct_orientation
from app.services.image_processing.perspective import correct_perspective
from app.services.image_processing.resolution import normalize_resolution
from app.services.image_processing.sharpen import sharpen

DEFAULT_STEP_ORDER: tuple[str, ...] = (
    "orientation",
    "deskew",
    "margin_trim",
    "resolution",
    "denoise",
    "contrast",
    "brightness",
)

# Module 12 additions: available (via `OCRConfiguration.preprocessing_steps`)
# but deliberately excluded from DEFAULT_STEP_ORDER so the existing
# pipeline's default/tested behavior is unchanged.
_STEP_FUNCTIONS: dict[str, Callable[[np.ndarray], np.ndarray]] = {
    "orientation": correct_orientation,
    "deskew": deskew,
    "margin_trim": trim_margins,
    "resolution": normalize_resolution,
    "denoise": denoise,
    "contrast": enhance_contrast,
    "brightness": correct_brightness,
    "perspective": correct_perspective,
    "adaptive_threshold": adaptive_threshold,
    "sharpen": sharpen,
    "background_clean": clean_background,
}


class PreprocessingPipeline:
    def __init__(self, steps: list[str] | None = None) -> None:
        self.steps = steps if steps is not None else list(DEFAULT_STEP_ORDER)
        unknown = set(self.steps) - _STEP_FUNCTIONS.keys()
        if unknown:
            raise ValueError(f"Unknown preprocessing step(s): {sorted(unknown)}")

    def run(self, image: np.ndarray) -> np.ndarray:
        result = image
        for step_name in self.steps:
            result = _STEP_FUNCTIONS[step_name](result)
        return result


def available_step_names() -> list[str]:
    return list(_STEP_FUNCTIONS.keys())
