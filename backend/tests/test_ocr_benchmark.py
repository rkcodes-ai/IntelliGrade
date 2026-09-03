"""Unit + API tests for the OCR benchmark module (Module 12): the
provider-comparison service and its `POST /ocr-providers/benchmark`
endpoint. Only Tesseract is guaranteed runnable in every test environment
(see `tests/test_ocr_providers.py`'s module docstring) -- every assertion
here is written to hold regardless of which of the other five providers
happen to be installed/configured in the environment the suite runs in."""

import numpy as np
from httpx import AsyncClient
from PIL import Image, ImageDraw
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.image_processing.io_utils import encode_image_to_bytes, save_image
from app.services.ocr_benchmark_service import (
    OCRBenchmarkService,
    _character_accuracy,
    _edit_distance,
    _word_accuracy,
)
from tests.conftest import auth_headers, create_test_user
from tests.test_ocr_providers_api import _create_institution, _institution_headers, _login


def _text_image_path(tmp_path) -> str:
    image = Image.new("RGB", (400, 200), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 40), "HELLO WORLD", fill="black")
    draw.text((20, 90), "SECOND LINE HERE", fill="black")
    path = str(tmp_path / "sample.png")
    save_image(np.array(image), path)
    return path


def _text_image_bytes() -> bytes:
    image = Image.new("RGB", (400, 200), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 40), "HELLO WORLD", fill="black")
    return encode_image_to_bytes(np.array(image))


# --- Edit distance / accuracy helpers ---------------------------------------


def test_edit_distance_identical_sequences_is_zero() -> None:
    assert _edit_distance(["a", "b", "c"], ["a", "b", "c"]) == 0


def test_edit_distance_counts_substitutions() -> None:
    assert _edit_distance(["a", "b", "c"], ["a", "x", "c"]) == 1


def test_edit_distance_counts_insertions_and_deletions() -> None:
    assert _edit_distance(["a", "b"], ["a", "b", "c"]) == 1
    assert _edit_distance(["a", "b", "c"], ["a", "b"]) == 1


def test_word_accuracy_perfect_match_is_one() -> None:
    assert _word_accuracy("hello world", "hello world") == 1.0


def test_word_accuracy_penalizes_mismatches() -> None:
    accuracy = _word_accuracy("hello there", "hello world")
    assert 0.0 <= accuracy < 1.0


def test_character_accuracy_perfect_match_is_one() -> None:
    assert _character_accuracy("hello", "hello") == 1.0


def test_character_accuracy_clamped_to_zero_minimum() -> None:
    accuracy = _character_accuracy("completely different text here", "hi")
    assert accuracy == 0.0


# --- OCRBenchmarkService ------------------------------------------------


def test_benchmark_service_runs_tesseract_successfully(tmp_path) -> None:
    service = OCRBenchmarkService()
    report = service.run(_text_image_path(tmp_path), provider_codes=["tesseract"])

    assert report.language == "eng"
    assert report.reference_text_supplied is False
    assert len(report.results) == 1
    result = report.results[0]
    assert result.provider_code == "tesseract"
    assert result.success is True
    assert result.error is None
    assert result.character_count > 0
    assert result.word_count > 0
    assert result.processing_time_seconds is not None
    assert result.processing_time_seconds >= 0.0
    assert result.word_accuracy is None  # no reference_text supplied
    assert result.character_accuracy is None


def test_benchmark_service_computes_accuracy_against_reference_text(tmp_path) -> None:
    service = OCRBenchmarkService()
    report = service.run(
        _text_image_path(tmp_path),
        provider_codes=["tesseract"],
        reference_text="HELLO WORLD\nSECOND LINE HERE",
    )

    assert report.reference_text_supplied is True
    result = report.results[0]
    assert result.word_accuracy is not None
    assert result.character_accuracy is not None
    assert 0.0 <= result.word_accuracy <= 1.0
    assert 0.0 <= result.character_accuracy <= 1.0


def test_benchmark_service_reports_unregistered_code_as_failure(tmp_path) -> None:
    service = OCRBenchmarkService()
    report = service.run(_text_image_path(tmp_path), provider_codes=["not-a-real-provider"])

    result = report.results[0]
    assert result.success is False
    assert result.error is not None
    assert result.character_count == 0


def test_benchmark_service_reports_cloud_provider_failure_without_crashing(tmp_path) -> None:
    """Azure/Google/AWS all raise `OCRProviderConfigurationError` without
    real credentials (see `tests/test_ocr_providers.py`) -- the benchmark
    run must surface that as one failed result, not blow up the whole run."""
    service = OCRBenchmarkService()
    report = service.run(_text_image_path(tmp_path), provider_codes=["tesseract", "azure_ocr"])

    assert len(report.results) == 2
    by_code = {r.provider_code: r for r in report.results}
    assert by_code["tesseract"].success is True
    assert by_code["azure_ocr"].success is False
    assert by_code["azure_ocr"].error is not None


def test_benchmark_service_defaults_to_every_registered_provider(tmp_path) -> None:
    service = OCRBenchmarkService()
    report = service.run(_text_image_path(tmp_path))

    codes = {r.provider_code for r in report.results}
    assert codes == {
        "tesseract",
        "easyocr",
        "paddleocr",
        "surya",
        "doctr",
        "trocr_handwritten",
        "azure_ocr",
        "google_vision",
        "aws_textract",
    }


# --- API ------------------------------------------------------------------


async def test_benchmark_endpoint_requires_permission(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="benchstudent1", role=seed_rbac["student"])
    institution = await _create_institution(db_session, code="BENCHSTU")
    token = await _login(client, "benchstudent1")

    response = await client.post(
        "/api/v1/ocr-providers/benchmark",
        headers=_institution_headers(token, institution.id),
        files={"file": ("sample.png", _text_image_bytes(), "image/png")},
        data={"provider_codes": "tesseract"},
    )

    assert response.status_code == 403


async def test_benchmark_endpoint_runs_requested_providers(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="benchadmin1", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="BENCHRUN")
    token = await _login(client, "benchadmin1")

    response = await client.post(
        "/api/v1/ocr-providers/benchmark",
        headers=_institution_headers(token, institution.id),
        files={"file": ("sample.png", _text_image_bytes(), "image/png")},
        data={"provider_codes": "tesseract"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reference_text_supplied"] is False
    assert len(body["results"]) == 1
    assert body["results"][0]["provider_code"] == "tesseract"
    assert body["results"][0]["success"] is True


async def test_benchmark_endpoint_defaults_to_all_providers(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="benchadmin2", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="BENCHALL")
    token = await _login(client, "benchadmin2")

    response = await client.post(
        "/api/v1/ocr-providers/benchmark",
        headers=_institution_headers(token, institution.id),
        files={"file": ("sample.png", _text_image_bytes(), "image/png")},
    )

    assert response.status_code == 200
    assert len(response.json()["results"]) == 9


async def test_benchmark_endpoint_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="benchadmin3", role=seed_rbac["super_admin"])
    token = await _login(client, "benchadmin3")

    response = await client.post(
        "/api/v1/ocr-providers/benchmark",
        headers=auth_headers(token),
        files={"file": ("sample.png", _text_image_bytes(), "image/png")},
        data={"provider_codes": "tesseract"},
    )

    assert response.status_code == 422
