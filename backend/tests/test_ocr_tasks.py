"""Tests for the Celery OCR pipeline orchestration in `app.tasks.ocr_tasks`.

Runs `_run_pipeline` directly (bypassing Celery itself, which is
process/broker plumbing already exercised elsewhere) against the real
image-processing pipeline and the real installed Tesseract binary, using
the per-test SQLite session and the fake in-memory storage bucket that
every other Module 05 test relies on (see `conftest.py`). `AsyncSessionLocal`
is monkeypatched in this module only, since `_run_pipeline` opens its own
session rather than accepting one as an argument (it's a Celery task body,
not a request-scoped service call).
"""

import uuid

import numpy as np
import pymupdf
import pytest
from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.answer_script import AnswerScript
from app.models.ocr_configuration import OCRConfiguration
from app.models.ocr_job import OCRJob
from app.models.ocr_provider import OCRProvider
from app.models.ocr_provider_candidate import OCRProviderCandidate
from app.models.ocr_result import OCRResult
from app.models.processing_history import ProcessingHistory
from app.services.image_processing.io_utils import encode_image_to_bytes
from app.services.ocr.base import OCRPageResult, OCRProviderAdapter
from app.services.ocr.exceptions import OCRProviderConfigurationError, OCRUnsupportedFormatError
from tests.conftest import _FAKE_BUCKET, create_test_user
from tests.test_answer_scripts_api import _create_exam_session


def _text_image_bytes() -> bytes:
    image = Image.new("RGB", (400, 200), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 80), "HELLO WORLD", fill="black")
    return encode_image_to_bytes(np.array(image), image_format="PNG")


def _non_blank_text_image_bytes() -> bytes:
    """Two lines of text, unlike `_text_image_bytes()`'s one -- enough ink
    to clear `is_blank_page()`'s 0.5% threshold (a single short line does
    not), for tests that need the pipeline to actually reach the OCR stage
    rather than take the blank-page shortcut."""
    image = Image.new("RGB", (400, 200), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 40), "HELLO WORLD", fill="black")
    draw.text((20, 90), "SECOND LINE HERE", fill="black")
    return encode_image_to_bytes(np.array(image), image_format="PNG")


async def _seed_tesseract_provider(db_session: AsyncSession) -> OCRProvider:
    provider = OCRProvider(
        code="tesseract",
        name="Tesseract OCR",
        is_enabled=True,
        is_implemented=True,
        is_default=True,
    )
    db_session.add(provider)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(provider)
    return provider


async def _make_answer_script(
    db_session: AsyncSession,
    *,
    code: str,
    mime_type: str = "image/png",
    image_bytes: bytes | None = None,
) -> AnswerScript:
    exam_session = await _create_exam_session(db_session, code=code)
    uploader = await create_test_user(db_session, username=f"uploader_{code.lower()}")

    storage_key = f"{exam_session.institution_id}/{uuid.uuid4()}/original/page.png"
    _FAKE_BUCKET[storage_key] = image_bytes if image_bytes is not None else _text_image_bytes()

    script = AnswerScript(
        institution_id=exam_session.institution_id,
        exam_session_id=exam_session.id,
        uploaded_by=uploader.id,
        original_filename="page.png",
        mime_type=mime_type,
        file_size_bytes=len(_FAKE_BUCKET[storage_key]),
        checksum_sha256="0" * 64,
        storage_key=storage_key,
        status="stored",
    )
    db_session.add(script)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(script)
    return script


@pytest.fixture(autouse=True)
def _bridge_ocr_tasks_session(monkeypatch: pytest.MonkeyPatch, db_engine) -> None:
    """`_run_pipeline` imports `AsyncSessionLocal` at module scope and opens
    its own session — point it at this test's in-memory SQLite engine
    instead of the real (unreachable) Postgres configuration."""
    session_factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )
    monkeypatch.setattr("app.tasks.ocr_tasks.AsyncSessionLocal", session_factory)


async def test_run_pipeline_completes_and_produces_structured_content(
    db_session: AsyncSession,
) -> None:
    from app.tasks.ocr_tasks import _run_pipeline

    await _seed_tesseract_provider(db_session)
    script = await _make_answer_script(db_session, code="PIPEOK")

    await _run_pipeline(str(script.id))

    await db_session.refresh(script)
    assert script.status == "completed"
    assert script.page_count == 1
    assert script.structured_content is not None
    assert script.structured_content["pages"][0]["page_number"] == 1

    jobs = (
        (await db_session.execute(select(OCRJob).where(OCRJob.answer_script_id == script.id)))
        .scalars()
        .all()
    )
    assert len(jobs) == 1
    assert jobs[0].status == "completed"

    history = (
        (
            await db_session.execute(
                select(ProcessingHistory).where(ProcessingHistory.answer_script_id == script.id)
            )
        )
        .scalars()
        .all()
    )
    stages = {row.stage for row in history}
    assert "preprocessing" in stages
    assert "ocr" in stages
    assert "structuring" in stages
    assert "completed" in stages


async def test_run_pipeline_persists_provider_metadata_on_ocr_result(
    db_session: AsyncSession,
) -> None:
    """Module 12: `OCRResultService.create_with_hierarchy()` now also
    records `provider_version`/`processing_time_ms`/`image_resolution` —
    verify the real pipeline run actually populates them, not just that the
    service accepts the kwargs (see `tests/test_ocr_results_api.py` for the
    service-level contract)."""
    from app.tasks.ocr_tasks import _run_pipeline

    await _seed_tesseract_provider(db_session)
    script = await _make_answer_script(
        db_session, code="PROVMETA", image_bytes=_non_blank_text_image_bytes()
    )

    await _run_pipeline(str(script.id))

    result = (await db_session.execute(select(OCRResult))).scalar_one()
    assert result.provider_version is not None
    assert result.processing_time_ms is not None
    assert result.processing_time_ms >= 0
    assert result.image_resolution is not None
    width, height = result.image_resolution.split("x")
    assert int(width) > 0
    assert int(height) > 0


async def test_run_pipeline_honors_ocr_provider_env_override(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`OCR_PROVIDER` (Module 12) must win over both the institution's
    `OCRConfiguration` and the catalog's `is_default` row — seed `easyocr`
    as the enabled default, force `OCR_PROVIDER=tesseract`, and confirm the
    job actually ran against `tesseract`."""
    from app.tasks import ocr_tasks
    from app.tasks.ocr_tasks import _run_pipeline

    tesseract = await _seed_tesseract_provider(db_session)
    tesseract.is_default = False
    easyocr = OCRProvider(
        code="easyocr", name="EasyOCR", is_enabled=True, is_implemented=True, is_default=True
    )
    db_session.add(easyocr)
    await db_session.commit()

    monkeypatch.setattr(ocr_tasks.settings, "OCR_PROVIDER", "tesseract")
    script = await _make_answer_script(db_session, code="ENVOVERRIDE")

    await _run_pipeline(str(script.id))

    await db_session.refresh(script)
    assert script.status == "completed"
    jobs = (
        (await db_session.execute(select(OCRJob).where(OCRJob.answer_script_id == script.id)))
        .scalars()
        .all()
    )
    assert len(jobs) == 1
    assert jobs[0].ocr_provider_id == tesseract.id


async def test_run_pipeline_uses_institution_ocr_configuration_override(
    db_session: AsyncSession,
) -> None:
    from app.tasks.ocr_tasks import _run_pipeline

    tesseract = await _seed_tesseract_provider(db_session)
    other = OCRProvider(
        code="easyocr", name="EasyOCR", is_enabled=True, is_implemented=False, is_default=False
    )
    db_session.add(other)
    await db_session.flush()

    script = await _make_answer_script(db_session, code="CFGOVERRIDE")

    db_session.add(
        OCRConfiguration(
            institution_id=script.institution_id,
            ocr_provider_id=tesseract.id,
            assessment_id=None,
            is_active=True,
        )
    )
    await db_session.commit()

    await _run_pipeline(str(script.id))

    await db_session.refresh(script)
    assert script.status == "completed"


async def test_run_pipeline_marks_failed_when_no_provider_registered(
    db_session: AsyncSession,
) -> None:
    from app.tasks.ocr_tasks import _run_pipeline

    script = await _make_answer_script(db_session, code="NOPROVIDER")

    with pytest.raises(RuntimeError, match="not registered"):
        await _run_pipeline(str(script.id))

    await db_session.refresh(script)
    assert script.status == "failed"
    assert script.failure_reason is not None

    history = (
        (
            await db_session.execute(
                select(ProcessingHistory).where(ProcessingHistory.answer_script_id == script.id)
            )
        )
        .scalars()
        .all()
    )
    assert any(row.stage == "failed" for row in history)


async def test_run_pipeline_returns_early_for_missing_script() -> None:
    from app.tasks.ocr_tasks import _run_pipeline

    await _run_pipeline(str(uuid.uuid4()))


async def test_run_pipeline_returns_early_for_cancelled_script(db_session: AsyncSession) -> None:
    from app.tasks.ocr_tasks import _run_pipeline

    script = await _make_answer_script(db_session, code="CANCELLEDRUN")
    script.status = "cancelled"
    await db_session.commit()

    await _run_pipeline(str(script.id))

    await db_session.refresh(script)
    assert script.status == "cancelled"


class _AlwaysBrokenProvider(OCRProviderAdapter):
    """A real, in-memory `OCRProviderAdapter` (not a mock-library patch)
    that always raises a provider-level failure — used to exercise the
    Phase 12 fallback strategy deterministically, without depending on a
    genuinely misconfigured cloud provider."""

    provider_code = "always_broken"
    is_implemented = True

    def extract(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
        raise OCRProviderConfigurationError("simulated: this provider is not configured")


class _AlwaysContentErrorProvider(OCRProviderAdapter):
    """Raises a content-level (not provider-level) error — must NOT trigger
    fallback, since switching providers would never fix a corrupt/
    unsupported input."""

    provider_code = "always_content_error"
    is_implemented = True

    def extract(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
        raise OCRUnsupportedFormatError("simulated: unsupported format")


async def test_run_pipeline_falls_back_to_tesseract_on_provider_level_failure(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase 12 (Six-Provider OCR milestone): a provider-level failure
    (missing dependency/config/auth/connectivity/timeout/rate-limit) on the
    resolved primary provider must fall back once to `tesseract`, complete
    the job successfully, and record the fallback visibly on the `OCRJob`
    row — never silently."""
    from app.tasks import ocr_tasks
    from app.tasks.ocr_tasks import _run_pipeline

    tesseract = await _seed_tesseract_provider(db_session)
    tesseract.is_default = False
    broken = OCRProvider(
        code="always_broken",
        name="Always Broken",
        is_enabled=True,
        is_implemented=True,
        is_default=True,
    )
    db_session.add(broken)
    await db_session.commit()
    await db_session.refresh(broken)

    original_get_adapter = ocr_tasks.get_provider_adapter

    def fake_get_adapter(code: str):
        if code == "always_broken":
            return _AlwaysBrokenProvider()
        return original_get_adapter(code)

    monkeypatch.setattr(ocr_tasks, "get_provider_adapter", fake_get_adapter)

    script = await _make_answer_script(
        db_session, code="FALLBACKOK", image_bytes=_non_blank_text_image_bytes()
    )

    await _run_pipeline(str(script.id))

    await db_session.refresh(script)
    assert script.status == "completed"

    job = (
        (await db_session.execute(select(OCRJob).where(OCRJob.answer_script_id == script.id)))
        .scalars()
        .first()
    )
    assert job.status == "completed"
    assert job.ocr_provider_id == tesseract.id
    assert job.requested_ocr_provider_id == broken.id
    assert job.fallback_reason is not None
    assert "not configured" in job.fallback_reason


async def test_run_pipeline_does_not_fall_back_on_content_level_failure(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.tasks import ocr_tasks
    from app.tasks.ocr_tasks import _run_pipeline

    tesseract = await _seed_tesseract_provider(db_session)
    tesseract.is_default = False
    broken = OCRProvider(
        code="always_content_error",
        name="Always Content Error",
        is_enabled=True,
        is_implemented=True,
        is_default=True,
    )
    db_session.add(broken)
    await db_session.commit()

    original_get_adapter = ocr_tasks.get_provider_adapter

    def fake_get_adapter(code: str):
        if code == "always_content_error":
            return _AlwaysContentErrorProvider()
        return original_get_adapter(code)

    monkeypatch.setattr(ocr_tasks, "get_provider_adapter", fake_get_adapter)

    script = await _make_answer_script(
        db_session, code="NOFALLBACK", image_bytes=_non_blank_text_image_bytes()
    )

    with pytest.raises(OCRUnsupportedFormatError):
        await _run_pipeline(str(script.id))

    await db_session.refresh(script)
    assert script.status == "failed"

    job = (
        (await db_session.execute(select(OCRJob).where(OCRJob.answer_script_id == script.id)))
        .scalars()
        .first()
    )
    assert job.requested_ocr_provider_id is None
    assert job.fallback_reason is None


def _two_page_pdf_bytes() -> bytes:
    """A real, genuine 2-page PDF (via `pymupdf`) with distinct real text
    on each page — Phase 14 (Six-Provider OCR milestone): the pipeline's
    actual production use case is multi-page PDFs, not single images, so
    this exercises real PDF page-splitting through the full pipeline
    rather than only the isolated `extract_pages_as_images()` unit test in
    `test_image_processing.py`."""
    doc = pymupdf.open()
    page1 = doc.new_page(width=600, height=400)
    page1.insert_text((50, 100), "PAGE ONE CONTENT HERE", fontsize=24)
    page2 = doc.new_page(width=600, height=400)
    page2.insert_text((50, 100), "PAGE TWO CONTENT HERE", fontsize=24)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


async def test_run_pipeline_processes_a_real_multi_page_pdf_in_order(
    db_session: AsyncSession,
) -> None:
    from app.tasks.ocr_tasks import _run_pipeline

    await _seed_tesseract_provider(db_session)
    script = await _make_answer_script(
        db_session, code="PDFMULTI", mime_type="application/pdf", image_bytes=_two_page_pdf_bytes()
    )

    await _run_pipeline(str(script.id))

    await db_session.refresh(script)
    assert script.status == "completed"
    assert script.page_count == 2

    pages = script.structured_content["pages"]
    assert len(pages) == 2
    assert pages[0]["page_number"] == 1
    assert pages[1]["page_number"] == 2

    page1_text = " ".join(
        line["text"] for block in pages[0]["blocks"] for line in block["lines"]
    )
    page2_text = " ".join(
        line["text"] for block in pages[1]["blocks"] for line in block["lines"]
    )
    assert "PAGE" in page1_text.upper() and "ONE" in page1_text.upper()
    assert "PAGE" in page2_text.upper() and "TWO" in page2_text.upper()

    jobs = (
        (await db_session.execute(select(OCRJob).where(OCRJob.answer_script_id == script.id)))
        .scalars()
        .all()
    )
    assert len(jobs) == 1
    assert jobs[0].status == "completed"

    history_stages = {
        row.stage
        for row in (
            await db_session.execute(
                select(ProcessingHistory).where(ProcessingHistory.answer_script_id == script.id)
            )
        )
        .scalars()
        .all()
    }
    assert {"preprocessing", "ocr", "structuring", "completed"} <= history_stages


async def test_run_pipeline_ensemble_mode_fuses_real_tesseract_and_easyocr(
    db_session: AsyncSession,
) -> None:
    """Six-Provider OCR milestone — Ensemble Mode, opt-in path. Real
    Tesseract + real EasyOCR (both genuinely verified providers) run
    against the same real page image, fused by the real deterministic
    Fusion Engine, with every raw candidate preserved in
    `OCRProviderCandidate` rows — no mocks anywhere in this test."""
    from app.tasks.ocr_tasks import _run_pipeline

    tesseract = await _seed_tesseract_provider(db_session)
    easyocr = OCRProvider(
        code="easyocr", name="EasyOCR", is_enabled=True, is_implemented=True, is_default=False
    )
    db_session.add(easyocr)
    await db_session.flush()

    script = await _make_answer_script(
        db_session, code="ENSEMBLEOK", image_bytes=_non_blank_text_image_bytes()
    )

    db_session.add(
        OCRConfiguration(
            institution_id=script.institution_id,
            ocr_provider_id=tesseract.id,
            assessment_id=None,
            is_active=True,
            is_ensemble_enabled=True,
            ensemble_provider_codes=["tesseract", "easyocr"],
        )
    )
    await db_session.commit()

    await _run_pipeline(str(script.id))

    await db_session.refresh(script)
    assert script.status == "completed"

    result = (await db_session.execute(select(OCRResult))).scalar_one()
    assert result.is_ensemble_result is True
    assert set(result.contributing_provider_codes) == {"tesseract", "easyocr"}
    assert "HELLO" in result.raw_text.upper()

    candidates = (
        (
            await db_session.execute(
                select(OCRProviderCandidate).where(
                    OCRProviderCandidate.ocr_result_id == result.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert {c.provider_code for c in candidates} == {"tesseract", "easyocr"}
    assert all(c.status == "success" for c in candidates)
    assert all(c.raw_text is not None for c in candidates)


async def test_run_pipeline_ensemble_mode_tolerates_one_provider_failing(
    db_session: AsyncSession,
) -> None:
    from app.tasks.ocr_tasks import _run_pipeline

    tesseract = await _seed_tesseract_provider(db_session)
    broken = OCRProvider(
        code="always_broken_ensemble",
        name="Always Broken (ensemble)",
        is_enabled=True,
        is_implemented=True,
        is_default=False,
    )
    db_session.add(broken)
    await db_session.flush()

    script = await _make_answer_script(
        db_session, code="ENSEMBLEPARTIAL", image_bytes=_non_blank_text_image_bytes()
    )
    db_session.add(
        OCRConfiguration(
            institution_id=script.institution_id,
            ocr_provider_id=tesseract.id,
            assessment_id=None,
            is_active=True,
            is_ensemble_enabled=True,
            ensemble_provider_codes=["tesseract", "always_broken_ensemble"],
        )
    )
    await db_session.commit()

    await _run_pipeline(str(script.id))

    await db_session.refresh(script)
    # The registry has no "always_broken_ensemble" adapter class -- treated
    # as a failed candidate by `run_ensemble`, not a crash.
    assert script.status == "completed"

    result = (await db_session.execute(select(OCRResult))).scalar_one()
    assert result.contributing_provider_codes == ["tesseract"]

    candidates = (
        (
            await db_session.execute(
                select(OCRProviderCandidate).where(
                    OCRProviderCandidate.ocr_result_id == result.id
                )
            )
        )
        .scalars()
        .all()
    )
    by_code = {c.provider_code: c for c in candidates}
    assert by_code["tesseract"].status == "success"
    assert by_code["always_broken_ensemble"].status == "failed"
    assert by_code["always_broken_ensemble"].error_message is not None


async def test_run_pipeline_handles_blank_page(db_session: AsyncSession) -> None:
    from app.tasks.ocr_tasks import _run_pipeline

    await _seed_tesseract_provider(db_session)
    exam_session = await _create_exam_session(db_session, code="BLANKPIPE")
    uploader = await create_test_user(db_session, username="uploader_blankpipe")

    blank = np.full((200, 300, 3), 255, dtype=np.uint8)
    storage_key = f"{exam_session.institution_id}/{uuid.uuid4()}/original/blank.png"
    _FAKE_BUCKET[storage_key] = encode_image_to_bytes(blank, image_format="PNG")

    script = AnswerScript(
        institution_id=exam_session.institution_id,
        exam_session_id=exam_session.id,
        uploaded_by=uploader.id,
        original_filename="blank.png",
        mime_type="image/png",
        file_size_bytes=len(_FAKE_BUCKET[storage_key]),
        checksum_sha256="1" * 64,
        storage_key=storage_key,
        status="stored",
    )
    db_session.add(script)
    await db_session.commit()
    await db_session.refresh(script)

    await _run_pipeline(str(script.id))

    await db_session.refresh(script)
    assert script.status == "completed"
    assert script.structured_content["pages"][0]["blocks"] == []
