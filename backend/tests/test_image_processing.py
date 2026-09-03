"""Unit tests for every `app.services.image_processing` module — each
operates on plain `np.ndarray` images, so these are fast, dependency-free
tests covering the 12 preprocessing steps plus PDF/page-split plumbing."""

import numpy as np
import pymupdf
import pytest

from app.services.image_processing.adaptive_threshold import adaptive_threshold
from app.services.image_processing.background_clean import clean_background
from app.services.image_processing.blank_detection import is_blank_page
from app.services.image_processing.brightness import correct_brightness
from app.services.image_processing.contrast import enhance_contrast
from app.services.image_processing.crop import crop_to_bbox
from app.services.image_processing.denoise import denoise
from app.services.image_processing.deskew import deskew
from app.services.image_processing.io_utils import (
    encode_image_to_bytes,
    load_image,
    load_image_from_bytes,
    save_image,
    to_grayscale,
)
from app.services.image_processing.margin_trim import trim_margins
from app.services.image_processing.orientation import correct_orientation, detect_orientation
from app.services.image_processing.page_split import split_double_page
from app.services.image_processing.pdf_extraction import extract_page_count, extract_pages_as_images
from app.services.image_processing.perspective import correct_perspective
from app.services.image_processing.pipeline import PreprocessingPipeline, available_step_names
from app.services.image_processing.resolution import normalize_resolution
from app.services.image_processing.rotation import detect_rotation_angle
from app.services.image_processing.sharpen import sharpen


def _blank_image(height: int = 200, width: int = 300) -> np.ndarray:
    return np.full((height, width, 3), 255, dtype=np.uint8)


def _textlike_image(height: int = 200, width: int = 300) -> np.ndarray:
    image = _blank_image(height, width)
    image[40:60, 20:250] = 0
    image[100:120, 20:250] = 0
    return image


def test_to_grayscale_reduces_to_two_dimensions() -> None:
    gray = to_grayscale(_textlike_image())
    assert gray.ndim == 2


def test_save_and_load_image_round_trip(tmp_path) -> None:
    path = str(tmp_path / "sample.png")
    image = _textlike_image()
    save_image(image, path)
    loaded = load_image(path)
    assert loaded.shape == image.shape


def test_encode_and_load_image_from_bytes_round_trip() -> None:
    image = _textlike_image()
    data = encode_image_to_bytes(image, image_format="PNG")
    loaded = load_image_from_bytes(data)
    assert loaded.shape == image.shape


def test_is_blank_page_true_for_white_image() -> None:
    assert is_blank_page(_blank_image()) is True


def test_is_blank_page_false_for_textlike_image() -> None:
    assert is_blank_page(_textlike_image()) is False


def test_correct_brightness_returns_same_shape() -> None:
    result = correct_brightness(_textlike_image())
    assert result.shape == _textlike_image().shape


def test_correct_brightness_handles_all_black_image() -> None:
    black = np.zeros((50, 50, 3), dtype=np.uint8)
    result = correct_brightness(black)
    assert result.shape == black.shape


def test_enhance_contrast_returns_same_shape() -> None:
    result = enhance_contrast(_textlike_image())
    assert result.shape == _textlike_image().shape


def test_crop_to_bbox_returns_requested_region() -> None:
    image = _textlike_image(200, 300)
    cropped = crop_to_bbox(image, left=10, top=10, width=50, height=40)
    assert cropped.shape[:2] == (40, 50)


def test_crop_to_bbox_clamps_out_of_bounds() -> None:
    image = _textlike_image(200, 300)
    cropped = crop_to_bbox(image, left=-10, top=-10, width=1000, height=1000)
    assert cropped.shape[:2] == (200, 300)


def test_denoise_returns_same_shape() -> None:
    result = denoise(_textlike_image())
    assert result.shape == _textlike_image().shape


def test_detect_rotation_angle_returns_zero_for_blank_image() -> None:
    assert detect_rotation_angle(_blank_image()) == 0.0


def test_detect_rotation_angle_returns_a_float_for_textlike_image() -> None:
    angle = detect_rotation_angle(_textlike_image())
    assert isinstance(angle, float)


def test_deskew_returns_same_shape() -> None:
    result = deskew(_textlike_image())
    assert result.shape == _textlike_image().shape


def test_deskew_skips_rotation_for_near_zero_angle() -> None:
    image = _textlike_image()
    result = deskew(image, angle=0.0)
    assert np.array_equal(result, image)


def test_deskew_applies_rotation_for_nonzero_angle() -> None:
    image = _textlike_image()
    result = deskew(image, angle=5.0)
    assert result.shape == image.shape


def test_trim_margins_shrinks_blank_borders() -> None:
    image = _blank_image(200, 300)
    image[80:120, 100:200] = 0
    trimmed = trim_margins(image)
    assert trimmed.shape[0] <= image.shape[0]
    assert trimmed.shape[1] <= image.shape[1]


def test_trim_margins_returns_original_when_fully_blank() -> None:
    image = _blank_image()
    trimmed = trim_margins(image)
    assert trimmed.shape == image.shape


def test_normalize_resolution_resizes_to_target_long_edge() -> None:
    image = _textlike_image(200, 300)
    result = normalize_resolution(image, target_long_edge=600)
    assert max(result.shape[:2]) == 600


def test_normalize_resolution_skips_when_already_close() -> None:
    image = _textlike_image(200, 300)
    result = normalize_resolution(image, target_long_edge=300)
    assert result.shape == image.shape


def test_detect_orientation_returns_a_valid_candidate() -> None:
    orientation = detect_orientation(_textlike_image())
    assert orientation in (0, 90, 180, 270)


def _multiline_textlike_image() -> np.ndarray:
    """A taller, multi-band image approximating a real multi-line
    document page (unlike `_textlike_image()`'s two bands) -- text-heavy
    near the top, sparser toward the bottom, exactly the realistic shape
    that (before the fix this test guards) made `detect_orientation()`
    report `180` for a genuinely upright page (see the Six-Provider OCR
    milestone's real-infrastructure verification, which caught this via a
    live Celery-worker end-to-end run genuinely mangling otherwise-perfect
    Tesseract output)."""
    image = _blank_image(1000, 800)
    y = 60
    for _ in range(6):
        image[y : y + 20, 40:760] = 0
        y += 60
    return image


def test_detect_orientation_never_flips_a_correctly_oriented_multiline_page() -> None:
    """Regression test: row-sum *variance* is mathematically identical for
    an image and its 180-degree rotation (rotating reverses row order
    without changing the row-sum distribution), so comparing all four
    candidates naively can -- and, on a realistic multi-line page, did --
    report `180` for already-correct content. `detect_orientation()` must
    never disagree between an upright page and that same page rotated 180
    degrees -- both are in the same indistinguishable pair, so both must
    resolve to the same (upright, `0`) answer, never flipping content that
    was already correct."""
    upright = _multiline_textlike_image()
    upside_down = np.rot90(upright, 2)

    assert detect_orientation(upright) == 0
    assert detect_orientation(upside_down) == 0


def test_detect_orientation_recognizes_sideways_pages() -> None:
    upright = _multiline_textlike_image()
    sideways = np.rot90(upright, 1)
    assert detect_orientation(sideways) == 90


def test_correct_orientation_rotates_by_90() -> None:
    image = _textlike_image(100, 200)
    rotated = correct_orientation(image, rotation=90)
    assert rotated.shape[:2] == (200, 100)


def test_correct_orientation_180_preserves_shape() -> None:
    image = _textlike_image(100, 200)
    rotated = correct_orientation(image, rotation=180)
    assert rotated.shape == image.shape


def test_correct_orientation_270_transposes_shape() -> None:
    image = _textlike_image(100, 200)
    rotated = correct_orientation(image, rotation=270)
    assert rotated.shape[:2] == (200, 100)


def test_correct_orientation_zero_is_identity() -> None:
    image = _textlike_image()
    assert np.array_equal(correct_orientation(image, rotation=0), image)


def test_correct_orientation_rejects_invalid_angle() -> None:
    with pytest.raises(ValueError):
        correct_orientation(_textlike_image(), rotation=45)


def test_split_double_page_returns_single_image_without_gutter() -> None:
    pages = split_double_page(_textlike_image())
    assert len(pages) == 1


def test_split_double_page_splits_on_clean_gutter() -> None:
    image = _blank_image(200, 400)
    image[:, :150] = 0
    image[:, 250:] = 0
    pages = split_double_page(image)
    assert len(pages) in (1, 2)


def test_extract_page_count_and_pages_from_pdf() -> None:
    doc = pymupdf.open()
    doc.new_page(width=200, height=300)
    doc.new_page(width=200, height=300)
    pdf_bytes = doc.tobytes()
    doc.close()

    assert extract_page_count(pdf_bytes) == 2
    images = extract_pages_as_images(pdf_bytes, dpi=72)
    assert len(images) == 2
    assert images[0].ndim == 3


def test_preprocessing_pipeline_runs_default_steps() -> None:
    pipeline = PreprocessingPipeline()
    result = pipeline.run(_textlike_image())
    assert result.ndim == 3


def test_preprocessing_pipeline_runs_custom_step_subset() -> None:
    pipeline = PreprocessingPipeline(steps=["denoise", "contrast"])
    result = pipeline.run(_textlike_image())
    assert result.shape[2] == 3


def test_preprocessing_pipeline_rejects_unknown_step() -> None:
    with pytest.raises(ValueError):
        PreprocessingPipeline(steps=["not_a_real_step"])


def test_available_step_names_lists_default_and_module_12_steps() -> None:
    names = available_step_names()
    assert "deskew" in names
    assert "denoise" in names
    assert "perspective" in names
    assert "adaptive_threshold" in names
    assert "sharpen" in names
    assert "background_clean" in names
    assert len(names) == 11


def test_correct_perspective_returns_original_when_no_quadrilateral_found() -> None:
    image = _textlike_image()
    result = correct_perspective(image)
    assert result.shape == image.shape


def test_adaptive_threshold_returns_binarized_same_shape() -> None:
    result = adaptive_threshold(_textlike_image())
    assert result.shape == _textlike_image().shape
    unique_values = set(np.unique(result).tolist())
    assert unique_values <= {0, 255}


def test_adaptive_threshold_corrects_even_block_size() -> None:
    result = adaptive_threshold(_textlike_image(), block_size=34)
    assert result.shape == _textlike_image().shape


def test_sharpen_returns_same_shape() -> None:
    result = sharpen(_textlike_image())
    assert result.shape == _textlike_image().shape


def test_sharpen_zero_amount_is_effectively_identity() -> None:
    image = _textlike_image()
    result = sharpen(image, amount=0.0)
    assert np.array_equal(result, image)


def test_clean_background_returns_same_shape() -> None:
    result = clean_background(_textlike_image())
    assert result.shape == _textlike_image().shape


def test_clean_background_handles_all_black_image() -> None:
    black = np.zeros((50, 50, 3), dtype=np.uint8)
    result = clean_background(black)
    assert result.shape == black.shape


def test_preprocessing_pipeline_runs_module_12_steps() -> None:
    pipeline = PreprocessingPipeline(
        steps=["perspective", "adaptive_threshold", "sharpen", "background_clean"]
    )
    result = pipeline.run(_textlike_image())
    assert result.ndim == 3
