"""Tests for the Module 06 official-document ingestion pipeline
orchestration in `app.tasks.official_document_tasks`.

Runs `_run_pipeline` directly (bypassing Celery itself, for the same
reason `tests/test_ocr_tasks.py` does — see `KNOWN_LIMITATIONS.md`)
against the real image-processing pipeline and the real installed
Tesseract binary, using the per-test SQLite session and the fake
in-memory storage bucket every Module 05/06 test relies on.
"""

import uuid

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.extracted_model_answer import ExtractedModelAnswer
from app.models.extracted_question import ExtractedQuestion
from app.models.mark_scheme_range import MarkSchemeRange
from app.models.official_exam_document import OfficialExamDocument
from app.services.image_processing.io_utils import encode_image_to_bytes
from tests.conftest import _FAKE_BUCKET, create_test_user
from tests.test_official_exam_documents_api import _create_exam


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in ("arial.ttf", "C:/Windows/Fonts/arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _render_lines(lines: list[str], *, size: tuple[int, int] = (900, 400)) -> bytes:
    image = Image.new("RGB", size, color="white")
    draw = ImageDraw.Draw(image)
    font = _font(28)
    for index, line in enumerate(lines):
        draw.text((20, 20 + index * 50), line, fill="black", font=font)
    return encode_image_to_bytes(np.array(image), image_format="PNG")


async def _make_document(
    db_session: AsyncSession, *, code: str, document_type: str, image_bytes: bytes
) -> OfficialExamDocument:
    exam = await _create_exam(db_session, code=code)
    uploader = await create_test_user(db_session, username=f"oedtaskuploader_{code.lower()}")

    storage_key = f"official-exam-documents/{exam.institution_id}/{uuid.uuid4()}/original/doc.png"
    _FAKE_BUCKET[storage_key] = image_bytes

    document = OfficialExamDocument(
        institution_id=exam.institution_id,
        exam_id=exam.id,
        uploaded_by=uploader.id,
        document_type=document_type,
        original_filename="doc.png",
        mime_type="image/png",
        file_size_bytes=len(image_bytes),
        checksum_sha256="0" * 64,
        storage_key=storage_key,
        ocr_status="stored",
        verification_status="not_started",
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document


@pytest.fixture(autouse=True)
def _bridge_official_document_tasks_session(monkeypatch: pytest.MonkeyPatch, db_engine) -> None:
    """`_run_pipeline` imports `AsyncSessionLocal` at module scope and
    opens its own session — point it at this test's in-memory SQLite
    engine instead of the real (unreachable) Postgres configuration, same
    approach as `tests/test_ocr_tasks.py`."""
    session_factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )
    monkeypatch.setattr("app.tasks.official_document_tasks.AsyncSessionLocal", session_factory)


async def test_run_pipeline_extracts_questions_from_question_paper(
    db_session: AsyncSession,
) -> None:
    from app.tasks.official_document_tasks import _run_pipeline

    image_bytes = _render_lines(
        [
            "Q1) Explain the process of photosynthesis in plants. [2]",
            "Q2) What is the powerhouse of the cell? (1 mark)",
            "Q3) Describe Newtons three laws of motion. - 5 marks",
        ]
    )
    document = await _make_document(
        db_session, code="TASKQP", document_type="question_paper", image_bytes=image_bytes
    )

    await _run_pipeline(str(document.id))

    await db_session.refresh(document)
    assert document.ocr_status == "completed"
    assert document.page_count == 1
    assert document.raw_ocr_text is not None
    assert "photosynthesis" in document.raw_ocr_text.lower()

    questions = (
        (
            await db_session.execute(
                select(ExtractedQuestion)
                .where(ExtractedQuestion.document_id == document.id)
                .order_by(ExtractedQuestion.display_order)
            )
        )
        .scalars()
        .all()
    )
    assert [q.question_number for q in questions] == ["1", "2", "3"]
    assert questions[0].detected_marks == 2
    assert questions[0].verification_status == "pending"


async def test_run_pipeline_extracts_answers_from_model_answer_document(
    db_session: AsyncSession,
) -> None:
    from app.tasks.official_document_tasks import _run_pipeline

    image_bytes = _render_lines(
        [
            "1) Photosynthesis converts light energy into chemical energy.",
            "2) The mitochondria is the powerhouse of the cell.",
        ]
    )
    document = await _make_document(
        db_session, code="TASKMA", document_type="model_answer", image_bytes=image_bytes
    )

    await _run_pipeline(str(document.id))

    await db_session.refresh(document)
    assert document.ocr_status == "completed"

    answers = (
        (
            await db_session.execute(
                select(ExtractedModelAnswer).where(ExtractedModelAnswer.document_id == document.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(answers) == 2
    assert {a.question_number for a in answers} == {"1", "2"}


async def test_run_pipeline_extracts_ranges_from_mark_scheme_document(
    db_session: AsyncSession,
) -> None:
    from app.tasks.official_document_tasks import _run_pipeline

    image_bytes = _render_lines(
        ["Mark Scheme", "Questions 1-2 = 1 mark each", "Question 3 to 3 carries 5 marks"]
    )
    document = await _make_document(
        db_session, code="TASKMS", document_type="mark_scheme", image_bytes=image_bytes
    )

    await _run_pipeline(str(document.id))

    await db_session.refresh(document)
    assert document.ocr_status == "completed"

    ranges = (
        (
            await db_session.execute(
                select(MarkSchemeRange).where(MarkSchemeRange.document_id == document.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(ranges) == 2
    assert ranges[0].question_range_start == "1"
    assert ranges[0].question_range_end == "2"
    assert ranges[0].marks_per_question == 1
    assert ranges[1].marks_per_question == 5


async def test_run_pipeline_returns_early_for_missing_document() -> None:
    from app.tasks.official_document_tasks import _run_pipeline

    await _run_pipeline(str(uuid.uuid4()))


async def test_run_pipeline_returns_early_for_cancelled_document(db_session: AsyncSession) -> None:
    from app.tasks.official_document_tasks import _run_pipeline

    image_bytes = _render_lines(["Q1) Some question text."])
    document = await _make_document(
        db_session, code="TASKCANCEL", document_type="question_paper", image_bytes=image_bytes
    )
    document.ocr_status = "cancelled"
    await db_session.commit()

    await _run_pipeline(str(document.id))

    await db_session.refresh(document)
    assert document.ocr_status == "cancelled"


async def test_run_pipeline_marks_failed_on_missing_storage_object(
    db_session: AsyncSession,
) -> None:
    from app.tasks.official_document_tasks import _run_pipeline

    exam = await _create_exam(db_session, code="TASKFAIL")
    uploader = await create_test_user(db_session, username="oedtaskuploader_fail")
    document = OfficialExamDocument(
        institution_id=exam.institution_id,
        exam_id=exam.id,
        uploaded_by=uploader.id,
        document_type="question_paper",
        original_filename="missing.png",
        mime_type="image/png",
        file_size_bytes=10,
        checksum_sha256="1" * 64,
        storage_key="official-exam-documents/does/not/exist.png",
        ocr_status="stored",
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    with pytest.raises(KeyError):
        await _run_pipeline(str(document.id))

    await db_session.refresh(document)
    assert document.ocr_status == "failed"
    assert document.failure_reason is not None
