"""
Celery task driving Official Exam Document ingestion (Module 06): image
preprocessing, OCR extraction, and question/answer/mark-range extraction
for Exam-Cell-prepared PDFs (Question Paper / Model Answer / Mark
Scheme). See ADR-035/ADR-036.

This is a NEW, parallel task to Module 05's `app.tasks.ocr_tasks` — it
calls the exact same engine-layer functions
(`PreprocessingPipeline`, `get_provider_adapter`, `extract_pages_as_images`,
`normalize_text`, `StorageService`) but owns its own orchestration and its
own root entity (`OfficialExamDocument`, exam-scoped, not
`AnswerScript`/session-scoped). `app/tasks/ocr_tasks.py` is not imported
from or modified — see ADR-036 for why these are siblings, not a
base/subclass relationship.

Unlike Module 05's pipeline, this task does NOT persist a full
`OCRResult`/`OCRBlock`/`OCRLine`/`OCRWord` hierarchy — a question paper's
useful output is the per-question/per-answer/per-range *structured
extraction*, not a bounding-box-level tree, so each page's OCR text is
normalized and concatenated into `OfficialExamDocument.raw_ocr_text`
(write-once, per ADR-035), then handed to
`app.services.official_document_extraction_service`'s heuristics to
produce the child rows a teacher verifies.

This module explicitly does NOT evaluate, score, or grade any content —
see `app.services.ai`/`app.tasks.answer_evaluation_tasks` (a separate
module) for AI evaluation, which runs only after a teacher has verified
this ingestion's output.
"""

import asyncio
import tempfile
import uuid
from pathlib import Path

from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models.extracted_model_answer import ExtractedModelAnswer
from app.models.extracted_question import ExtractedQuestion
from app.models.mark_scheme_range import MarkSchemeRange
from app.models.official_exam_document import OfficialExamDocument
from app.services.image_processing.blank_detection import is_blank_page
from app.services.image_processing.io_utils import encode_image_to_bytes, load_image_from_bytes
from app.services.image_processing.pdf_extraction import extract_pages_as_images
from app.services.image_processing.pipeline import PreprocessingPipeline
from app.services.ocr.base import OCRPageResult
from app.services.ocr.registry import get_provider_adapter
from app.services.official_document_extraction_service import (
    extract_answers_from_text,
    extract_mark_ranges_from_text,
    extract_questions_from_text,
)
from app.services.official_document_storage_keys import build_official_document_page_key
from app.services.official_exam_document_page_service import OfficialExamDocumentPageService
from app.services.storage_service import StorageService
from app.services.text_normalization_service import normalize_text
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)

_DEFAULT_LANGUAGE = "eng"
# Hardcoded to Module 05's one real provider rather than resolved via a
# per-institution `OCRConfiguration`/`AIConfiguration` lookup (unlike
# `app.tasks.ocr_tasks`) — a deliberate first-pass simplification, not a
# design constraint: official documents are low-volume, faculty-uploaded
# artifacts where institution-level OCR-engine choice matters less than
# for high-volume student answer scripts. Revisit if that changes.
_OCR_PROVIDER_CODE = "tesseract"


def _page_text_from_result(page_result: OCRPageResult) -> str:
    """Reconstructs natural, line-broken text from `OCRPageResult.blocks`
    rather than using `page_result.raw_text` directly. `TesseractProvider`
    (Module 05, frozen) builds `raw_text` as one *word* per line
    (`"\\n".join(text_parts)` over individually-recognized words) —
    reasonable for that module's own consumer (the persisted
    `OCRBlock`/`OCRLine`/`OCRWord` tree, which never reads `raw_text` as
    prose), but this module feeds text directly into regex-based
    question/answer boundary detection, where genuine printed-line breaks
    matter and word-level breaks don't. `OCRLineResult.text` (already
    `" ".join(words)` per real detected line, see `tesseract_provider.py`)
    is the right granularity to rebuild from, so this reads the same
    `OCRPageResult` every provider returns rather than adding any new OCR
    logic (ADR-036)."""
    lines = [line.text for block in page_result.blocks for line in block.lines]
    return "\n".join(lines)


# celery ships no py.typed marker, so mypy sees this decorator as untyped.
@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="official_document.process",
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=300,
)
def process_official_document_task(self: Task, document_id: str) -> None:
    """Entry point enqueued after a successful official-document upload —
    see `app/api/v1/endpoints/official_exam_documents.py`."""
    try:
        asyncio.run(_run_pipeline(document_id))
    except Exception as exc:  # noqa: BLE001 - Celery retry needs the original exception
        logger.error("official_document_pipeline_failed", document_id=document_id, error=str(exc))
        raise self.retry(exc=exc) from exc


async def _run_pipeline(document_id: str) -> None:
    doc_id = uuid.UUID(document_id)

    async with AsyncSessionLocal() as session:
        document = await session.get(OfficialExamDocument, doc_id)
        if document is None or document.ocr_status == "cancelled":
            return

        institution_id = document.institution_id
        storage = StorageService()
        page_service = OfficialExamDocumentPageService(session)

        try:
            # --- Image Processing: page extraction + preprocessing ---
            document.ocr_status = "preprocessing"
            await session.commit()

            assert document.storage_key is not None  # set at upload time
            original_bytes = await storage.get_bytes(document.storage_key)

            if document.mime_type == "application/pdf":
                page_images = extract_pages_as_images(original_bytes)
            else:
                page_images = [load_image_from_bytes(original_bytes)]

            document.page_count = len(page_images)
            await session.flush()

            # Excludes the "orientation" step (part of
            # `PreprocessingPipeline`'s default step list) — live
            # validation during this module's build found it produces a
            # false-positive 180-degree flip on clean, well-formed
            # single-column printed text (exactly what official exam
            # documents are), turning perfectly readable OCR input into
            # garbage. This is a config choice at the call site, not a
            # change to `orientation.py` itself (frozen Module 05, see
            # ADR-033's "swap/reorder/disable via config, not a code
            # change" design) — official documents are direct digital
            # scans from the Exam Cell, not photographed answer sheets,
            # so orientation correction is low-value here anyway.
            pipeline = PreprocessingPipeline(
                steps=["deskew", "denoise", "contrast", "brightness", "margin_trim", "resolution"]
            )
            processed_pages = []
            for index, raw_image in enumerate(page_images, start=1):
                blank = is_blank_page(raw_image)
                processed_image = raw_image if blank else pipeline.run(raw_image)
                page_bytes = encode_image_to_bytes(processed_image)
                page_key = build_official_document_page_key(
                    institution_id, document.id, index, "png"
                )
                await storage.put_bytes(page_key, page_bytes, "image/png")

                page = await page_service.create(
                    institution_id,
                    document.id,
                    page_number=index,
                    storage_key=page_key,
                    width_px=int(processed_image.shape[1]),
                    height_px=int(processed_image.shape[0]),
                    is_blank=blank,
                    created_by=document.uploaded_by,
                )
                await session.commit()
                processed_pages.append((page, processed_image, blank))

            # --- OCR Engine (reused exactly from Module 05) ---
            document.ocr_status = "ocr_running"
            await session.commit()
            adapter = get_provider_adapter(_OCR_PROVIDER_CODE)

            page_texts: list[str] = []
            for page, processed_image, blank in processed_pages:
                if blank:
                    page.status = "ocr_complete"
                    await session.commit()
                    continue

                page.status = "ocr_running"
                await session.flush()
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(encode_image_to_bytes(processed_image))
                    tmp_path = tmp.name
                try:
                    page_result = adapter.extract(tmp_path, language=_DEFAULT_LANGUAGE)
                finally:
                    Path(tmp_path).unlink(missing_ok=True)

                normalized = normalize_text(_page_text_from_result(page_result))
                page_texts.append(f"--- Page {page.page_number} ---\n{normalized}")
                page.status = "ocr_complete"
                await session.commit()

            # Write-once, per ADR-035 — never modified by any later
            # (teacher-verification) action.
            document.raw_ocr_text = "\n\n".join(page_texts)
            document.ocr_status = "ocr_complete"
            await session.flush()
            await session.commit()

            # --- Structured extraction (document-type specific) ---
            await _extract_structured_content(session, document)

            document.ocr_status = "completed"
            document.verification_status = "not_started"
            await session.commit()

        except Exception as exc:
            await session.rollback()
            failed_document = await session.get(OfficialExamDocument, doc_id)
            if failed_document is not None:
                failed_document.ocr_status = "failed"
                failed_document.failure_reason = str(exc)[:2000]
                await session.commit()
            raise


async def _extract_structured_content(
    session: AsyncSession, document: OfficialExamDocument
) -> None:
    """Dispatches to the right heuristic + child-table writer based on
    `document.document_type`. Every created row starts
    `verification_status="pending"` — nothing here is treated as
    authoritative until a teacher verifies it (Stage: Teacher
    Verification)."""
    raw_text = document.raw_ocr_text or ""

    if document.document_type == "question_paper":
        for order, question_candidate in enumerate(extract_questions_from_text(raw_text)):
            session.add(
                ExtractedQuestion(
                    institution_id=document.institution_id,
                    document_id=document.id,
                    question_number=question_candidate.question_number,
                    question_text=question_candidate.question_text,
                    raw_ocr_text=question_candidate.question_text,
                    detected_marks=question_candidate.detected_marks,
                    display_order=order,
                    created_by=document.uploaded_by,
                )
            )
    elif document.document_type == "model_answer":
        for order, answer_candidate in enumerate(extract_answers_from_text(raw_text)):
            session.add(
                ExtractedModelAnswer(
                    institution_id=document.institution_id,
                    document_id=document.id,
                    question_number=answer_candidate.question_number,
                    answer_text=answer_candidate.answer_text,
                    raw_ocr_text=answer_candidate.answer_text,
                    display_order=order,
                    created_by=document.uploaded_by,
                )
            )
    elif document.document_type == "mark_scheme":
        for order, range_candidate in enumerate(extract_mark_ranges_from_text(raw_text)):
            session.add(
                MarkSchemeRange(
                    institution_id=document.institution_id,
                    document_id=document.id,
                    question_range_start=range_candidate.question_range_start,
                    question_range_end=range_candidate.question_range_end,
                    marks_per_question=range_candidate.marks_per_question,
                    display_order=order,
                    created_by=document.uploaded_by,
                )
            )
    else:  # pragma: no cover - document_type is validated at upload time
        raise ValueError(f"Unknown document_type: {document.document_type!r}")

    await session.commit()
