"""
Celery tasks driving the OCR pipeline (Module 05, Stages 4-8): image
preprocessing, OCR extraction, text normalization, and structured-output
generation. This module is the first real `@celery_app.task` in the
codebase (`celery_app.py`'s `include=[]` predates this) — see ADR-026.

Celery tasks are synchronous; every service in this codebase is async
(SQLAlchemy async session). `asyncio.run(...)` bridges the two — a plain,
well-understood pattern for sync Celery workers calling async code, and
the simplest option given no async worker pool is configured (see
`docs/ocr-pipeline-guide.md`'s "Background Processing" section for the
trade-off this implies: one task instance blocks its worker slot for the
whole pipeline run, not just CPU-bound work).

This module explicitly does NOT evaluate, score, or grade any answer
content — it only produces `AnswerScript.structured_content` for a future
Module 06 to consume.
"""

import asyncio
import dataclasses
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

from celery import Task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models.answer_script import AnswerScript
from app.models.ocr_configuration import OCRConfiguration
from app.models.ocr_provider import OCRProvider
from app.schemas.ocr_job import OCRJobCreate
from app.services.answer_script_page_service import AnswerScriptPageService
from app.services.document_intelligence.compute_budget import should_analyze_region
from app.services.document_intelligence.diagram_analysis import analyze_diagram_region
from app.services.document_intelligence.enhancement import enhance_page
from app.services.document_intelligence.language_context_resolver import (
    resolve_post_ocr_context,
)
from app.services.document_intelligence.language_detection import (
    LANGUAGE_NAME_TO_LANGUAGETOOL_CODE,
    LANGUAGE_NAME_TO_OCR_CODE,
    FastTextLanguageDetector,
)
from app.services.document_intelligence.language_quality import analyze_language_quality
from app.services.document_intelligence.layout import DetectedRegion, detect_regions_surya
from app.services.document_intelligence.math_recognition import MathRecognitionAdapter
from app.services.document_intelligence.quality import PageQualityReport, analyze_page_quality
from app.services.document_intelligence.routing import extract_table_structure, preserve_region_crop
from app.services.document_intelligence.variant_selection import select_best_variant
from app.services.document_region_service import DocumentRegionService
from app.services.document_structure_service import build_page_structure, build_structured_content
from app.services.image_processing.blank_detection import is_blank_page
from app.services.image_processing.io_utils import encode_image_to_bytes, load_image_from_bytes
from app.services.image_processing.pdf_extraction import extract_pages_as_images
from app.services.ocr.ensemble import run_ensemble
from app.services.ocr.exceptions import (
    OCRDependencyMissingError,
    OCRProviderAuthenticationError,
    OCRProviderConfigurationError,
    OCRProviderConnectivityError,
    OCRProviderRateLimitError,
    OCRProviderTimeoutError,
)
from app.services.ocr.registry import get_provider_adapter
from app.services.ocr_job_service import OCRJobService
from app.services.ocr_result_service import OCRResultService
from app.services.processing_history_service import ProcessingHistoryService
from app.services.storage_service import StorageService, build_page_key, build_region_crop_key
from app.services.text_normalization_service import normalize_text
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)
settings = get_settings()

_DEFAULT_LANGUAGE = "eng"

# Step 4 milestone: one adapter instance reused across pages/regions in a
# single task invocation -- the adapter object itself is a thin wrapper
# (just an interpreter path); the actual pix2tex model is loaded fresh
# inside each isolated-runtime subprocess call, same architecture already
# accepted for Surya/docTR/TrOCR (see `isolated_runtime.py`).
_math_recognition_adapter = MathRecognitionAdapter()

# Step 4.2 milestone: same "one adapter instance, thin wrapper" pattern
# as `_math_recognition_adapter` above -- the fastText model itself
# loads fresh inside each isolated-runtime subprocess call.
_language_detector = FastTextLanguageDetector()

# Provider-level failures (Phase 12, Six-Provider OCR milestone): the
# provider itself is unusable right now (missing dependency, bad/absent
# credentials, unreachable, timing out, rate-limited) -- as opposed to
# content-level failures (`OCRUnsupportedFormatError`/
# `OCRCorruptedDocumentError`), which switching providers would never fix,
# so those are deliberately excluded and left to fail (and retry via
# Celery's own `self.retry`) exactly as before.
_PROVIDER_LEVEL_FAILURES = (
    OCRDependencyMissingError,
    OCRProviderConfigurationError,
    OCRProviderAuthenticationError,
    OCRProviderConnectivityError,
    OCRProviderTimeoutError,
    OCRProviderRateLimitError,
)
#: Always registered, always implemented, no credentials required -- the
#: one provider every environment genuinely has, so it's the single
#: fallback target rather than cascading through all six (Phase 12: "avoid
#: retry storms").
_FALLBACK_PROVIDER_CODE = "tesseract"

#: OCR Ensemble Mode (Six-Provider OCR milestone) local-provider codes --
#: used as the default "which providers to run" set when an institution
#: turns on `OCRConfiguration.is_ensemble_enabled` without listing explicit
#: `ensemble_provider_codes`. Deliberately local-only: silently defaulting
#: to also calling the three cloud providers would risk unexpected billing
#: the moment an institution flips one boolean on, which Section 29 of the
#: milestone brief explicitly warns against ("current account/billing
#: limitations are external... do not make real cloud API calls a
#: requirement"). An institution that wants a cloud provider in its
#: ensemble lists it explicitly in `ensemble_provider_codes`.
_LOCAL_ENSEMBLE_PROVIDER_CODES = (
    "tesseract",
    "easyocr",
    "paddleocr",
    "doctr",
    "surya",
    "trocr_handwritten",
)


# celery ships no py.typed marker, so mypy sees this decorator as untyped.
@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="ocr.process_answer_script",
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=300,
)
def process_answer_script_task(self: Task, answer_script_id: str) -> None:
    """Entry point enqueued by `POST /answer-scripts` (and `/retry`) after
    a successful upload — see `app/api/v1/endpoints/answer_scripts.py`."""
    try:
        asyncio.run(_run_pipeline(answer_script_id))
    except Exception as exc:  # noqa: BLE001 - Celery retry needs the original exception
        logger.error("ocr_pipeline_failed", answer_script_id=answer_script_id, error=str(exc))
        raise self.retry(exc=exc) from exc


async def _resolve_provider_code(session: AsyncSession, institution_id: uuid.UUID) -> str:
    """`OCR_PROVIDER` env var (Module 12), if set, overrides every other
    source — an operator-level escape hatch for forcing one engine
    (testing, incident response, a benchmark run) without touching the DB.
    Otherwise: institution-wide `OCRConfiguration` (nullable `assessment_id`)
    if one exists, else the catalog's `is_default` provider. Per-assessment
    configuration overrides are a future refinement — this module always
    processes at the institution-default level (see `docs/ocr-pipeline-
    guide.md`)."""
    if settings.OCR_PROVIDER:
        return settings.OCR_PROVIDER

    config_query = select(OCRConfiguration).where(
        OCRConfiguration.institution_id == institution_id,
        OCRConfiguration.assessment_id.is_(None),
        OCRConfiguration.is_active.is_(True),
        OCRConfiguration.deleted_at.is_(None),
    )
    configuration = (await session.execute(config_query)).scalars().first()
    if configuration is not None:
        provider = await session.get(OCRProvider, configuration.ocr_provider_id)
        if provider is not None:
            return str(provider.code)

    default_query = select(OCRProvider).where(
        OCRProvider.is_default.is_(True),
        OCRProvider.is_enabled.is_(True),
        OCRProvider.deleted_at.is_(None),
    )
    default_provider = (await session.execute(default_query)).scalars().first()
    if default_provider is not None:
        return str(default_provider.code)

    return "tesseract"  # last-resort fallback: always registered, always implemented


async def _resolve_ensemble_config(
    session: AsyncSession, institution_id: uuid.UUID
) -> tuple[bool, list[str]]:
    """Ensemble Mode (Six-Provider OCR milestone) is opt-in per
    institution, off by default -- returns `(False, [])` (meaning "use the
    single-provider path exactly as before") unless the institution's
    active, institution-wide `OCRConfiguration` row has
    `is_ensemble_enabled=True`. When enabled, resolves the concrete
    provider-code list: the configuration's own explicit
    `ensemble_provider_codes` if set, otherwise every registered,
    *enabled* code in `_LOCAL_ENSEMBLE_PROVIDER_CODES` (see that
    constant's docstring for why cloud providers are never a silent
    default)."""
    config_query = select(OCRConfiguration).where(
        OCRConfiguration.institution_id == institution_id,
        OCRConfiguration.assessment_id.is_(None),
        OCRConfiguration.is_active.is_(True),
        OCRConfiguration.deleted_at.is_(None),
    )
    configuration = (await session.execute(config_query)).scalars().first()
    if configuration is None or not configuration.is_ensemble_enabled:
        return False, []

    if configuration.ensemble_provider_codes:
        return True, list(configuration.ensemble_provider_codes)

    enabled_query = select(OCRProvider.code).where(
        OCRProvider.code.in_(_LOCAL_ENSEMBLE_PROVIDER_CODES),
        OCRProvider.is_enabled.is_(True),
        OCRProvider.deleted_at.is_(None),
    )
    enabled_codes = [row[0] for row in (await session.execute(enabled_query)).all()]
    return True, enabled_codes


def _serialize_page_structure(
    page_number: int, normalized_text: str, blocks: list[Any], lines: list[Any], words: list[Any]
) -> dict[str, object]:
    lines_by_block: dict[uuid.UUID, list[Any]] = {}
    for line in lines:
        lines_by_block.setdefault(line.ocr_block_id, []).append(line)
    words_by_line: dict[uuid.UUID, list[Any]] = {}
    for word in words:
        words_by_line.setdefault(word.ocr_line_id, []).append(word)

    block_dicts = [
        {
            "block_type": block.block_type,
            "reading_order": block.reading_order,
            "bbox": {
                "left": block.bbox_left,
                "top": block.bbox_top,
                "width": block.bbox_width,
                "height": block.bbox_height,
            },
            "confidence": float(block.confidence),
            "lines": [
                {
                    "text": line.text,
                    "reading_order": line.reading_order,
                    "words": [word.text for word in words_by_line.get(line.id, [])],
                }
                for line in lines_by_block.get(block.id, [])
            ],
        }
        for block in blocks
    ]
    return build_page_structure(
        page_number=page_number, normalized_text=normalized_text, blocks=block_dicts
    )


async def _run_pipeline(answer_script_id: str) -> None:
    script_id = uuid.UUID(answer_script_id)

    async with AsyncSessionLocal() as session:
        script = await session.get(AnswerScript, script_id)
        if script is None or script.status == "cancelled":
            return

        institution_id = script.institution_id
        storage = StorageService()
        history_service = ProcessingHistoryService(session)
        page_service = AnswerScriptPageService(session)
        result_service = OCRResultService(session)
        job_service = OCRJobService(session)

        async def transition(stage: str, to_status: str) -> None:
            from_status = script.status
            script.status = to_status
            await session.flush()
            await history_service.record(
                institution_id, script.id, stage=stage, from_status=from_status, to_status=to_status
            )
            await session.commit()

        try:
            provider_code = await _resolve_provider_code(session, institution_id)
            provider_query = select(OCRProvider).where(OCRProvider.code == provider_code)
            provider = (await session.execute(provider_query)).scalars().first()
            if provider is None:
                raise RuntimeError(f"OCR provider '{provider_code}' is not registered.")

            ensemble_enabled, ensemble_provider_codes = await _resolve_ensemble_config(
                session, institution_id
            )

            job = await job_service.create(
                institution_id,
                OCRJobCreate(answer_script_id=script.id, ocr_provider_id=provider.id),
                created_by=script.uploaded_by,
            )
            await session.commit()

            # --- Stage 4: Image Processing (page extraction + preprocessing) ---
            await transition("preprocessing", "preprocessing")
            assert script.storage_key is not None  # set at upload time, before this task ever runs
            original_bytes = await storage.get_bytes(script.storage_key)

            if script.mime_type == "application/pdf":
                page_images = extract_pages_as_images(original_bytes)
            else:
                page_images = [load_image_from_bytes(original_bytes)]

            script.page_count = len(page_images)
            await session.flush()

            document_region_service = DocumentRegionService(session)
            pages = []
            for index, raw_image in enumerate(page_images, start=1):
                blank = is_blank_page(raw_image)

                # --- Document Intelligence milestone: quality-driven
                # adaptive enhancement replaces the old unconditional
                # PreprocessingPipeline run. Every new stage fails safe to
                # the raw original image (Section 28: one optional
                # intelligence component must never break the core OCR
                # pipeline) -- a blank page skips this work entirely, same
                # as before. ---
                processed_image = raw_image
                quality_decimal: Decimal | None = None
                quality_classification: str | None = None
                quality_metrics: dict[str, Any] | None = None
                enhancement_metadata: dict[str, Any] | None = None
                quality: PageQualityReport | None = None

                if not blank:
                    try:
                        quality = analyze_page_quality(raw_image)
                        quality_decimal = Decimal(str(round(quality.quality_score, 2)))
                        quality_classification = quality.quality_classification
                        quality_metrics = quality.to_metrics_dict()
                    except Exception as exc:  # noqa: BLE001 - quality analysis is optional; never blocks OCR
                        logger.warning(
                            "document_intelligence_quality_analysis_failed",
                            page_number=index,
                            error=str(exc),
                        )
                        quality = None

                    if quality is not None:
                        try:
                            enhancement = enhance_page(raw_image, quality)
                            if enhancement.operations_applied:
                                selection = select_best_variant(
                                    raw_image,
                                    enhancement.image,
                                    operations_applied=enhancement.operations_applied,
                                    language=_DEFAULT_LANGUAGE,
                                )
                                processed_image = (
                                    enhancement.image
                                    if selection.selected == "enhanced"
                                    else raw_image
                                )
                                enhancement_metadata = {
                                    "operations_applied": enhancement.operations_applied,
                                    "profile": enhancement.profile,
                                    "processing_time_ms": enhancement.processing_time_ms,
                                    "selected_variant": selection.selected,
                                    "selection_reason": selection.reason,
                                    "original_confidence": selection.original_confidence,
                                    "enhanced_confidence": selection.enhanced_confidence,
                                }
                        except Exception as exc:  # noqa: BLE001 - enhancement is optional; fall back to original
                            logger.warning(
                                "document_intelligence_enhancement_failed",
                                page_number=index,
                                error=str(exc),
                            )
                            processed_image = raw_image

                original_key = build_page_key(institution_id, script.id, index, "png")
                await storage.put_bytes(original_key, encode_image_to_bytes(raw_image), "image/png")

                preprocessed_key: str | None = None
                if processed_image is not raw_image:
                    preprocessed_key = build_page_key(
                        institution_id, script.id, index, "preprocessed.png"
                    )
                    await storage.put_bytes(
                        preprocessed_key, encode_image_to_bytes(processed_image), "image/png"
                    )

                page = await page_service.create(
                    institution_id,
                    script.id,
                    page_number=index,
                    storage_key=original_key,
                    preprocessed_storage_key=preprocessed_key,
                    width_px=int(processed_image.shape[1]),
                    height_px=int(processed_image.shape[0]),
                    is_blank=blank,
                    quality_score=quality_decimal,
                    quality_classification=quality_classification,
                    quality_metrics=quality_metrics,
                    enhancement_metadata=enhancement_metadata,
                    created_by=script.uploaded_by,
                )
                await session.commit()

                # --- Layout/region detection (Document Intelligence
                # milestone) -- real Surya LayoutPredictor via the existing
                # isolated-runtime bridge. Failure here is never fatal to
                # the page (Section 28: layout detection failure -> the
                # page still proceeds through full-page OCR below,
                # unaffected). ---
                if not blank:
                    try:
                        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                            tmp.write(encode_image_to_bytes(processed_image))
                            layout_tmp_path = tmp.name
                        try:
                            regions: list[DetectedRegion] = detect_regions_surya(layout_tmp_path)
                        finally:
                            Path(layout_tmp_path).unlink(missing_ok=True)

                        if regions:
                            crop_storage_keys: dict[int, str] = {}
                            extra_metadata: dict[int, dict[str, Any]] = {}
                            analyzed_visual_count = 0
                            analyzed_math_count = 0
                            for region_index, region in enumerate(regions):
                                if region.region_type in ("DIAGRAM", "TABLE", "EQUATION"):
                                    crop_key = build_region_crop_key(
                                        institution_id, script.id, index, region_index
                                    )
                                    await storage.put_bytes(
                                        crop_key,
                                        preserve_region_crop(processed_image, region),
                                        "image/png",
                                    )
                                    crop_storage_keys[region_index] = crop_key

                                # --- Step 4 milestone: diagram/math/table
                                # structural evidence, one region at a time.
                                # Each analysis is independently wrapped --
                                # a single region's failure never aborts the
                                # page or the rest of its regions (Section
                                # 19/47's fallback-not-crash requirement);
                                # `should_analyze_region` is the one
                                # eco-efficiency + resource-budget gate
                                # (Section 6/54) that skips analysis for
                                # anything that isn't genuinely a diagram or
                                # equation, and caps runaway per-page counts. ---
                                if region.region_type == "DIAGRAM":
                                    if should_analyze_region(
                                        region,
                                        analyzed_visual_count=analyzed_visual_count,
                                        analyzed_math_count=analyzed_math_count,
                                    ):
                                        analyzed_visual_count += 1
                                        try:
                                            diagram_evidence = analyze_diagram_region(
                                                processed_image, region
                                            )
                                            extra_metadata[region_index] = (
                                                diagram_evidence.to_dict()
                                            )
                                        except Exception as exc:  # noqa: BLE001 - one diagram failing must not abort the page
                                            logger.warning(
                                                "document_intelligence_diagram_analysis_failed",
                                                page_number=index,
                                                region_index=region_index,
                                                error=str(exc),
                                            )
                                elif region.region_type == "EQUATION":
                                    if should_analyze_region(
                                        region,
                                        analyzed_visual_count=analyzed_visual_count,
                                        analyzed_math_count=analyzed_math_count,
                                    ):
                                        analyzed_math_count += 1
                                        try:
                                            box = region.bbox
                                            crop = processed_image[
                                                box.top : box.top + box.height,
                                                box.left : box.left + box.width,
                                            ]
                                            with tempfile.NamedTemporaryFile(
                                                suffix=".png", delete=False
                                            ) as crop_tmp:
                                                crop_tmp.write(encode_image_to_bytes(crop))
                                                crop_tmp_path = crop_tmp.name
                                            try:
                                                math_evidence = _math_recognition_adapter.recognize(
                                                    crop_tmp_path
                                                )
                                            finally:
                                                Path(crop_tmp_path).unlink(missing_ok=True)
                                            extra_metadata[region_index] = math_evidence.to_dict()
                                        except Exception as exc:  # noqa: BLE001 - one equation failing must not abort the page
                                            logger.warning(
                                                "document_intelligence_math_recognition_failed",
                                                page_number=index,
                                                region_index=region_index,
                                                error=str(exc),
                                            )
                                elif region.region_type == "TABLE":
                                    try:
                                        table_structure = extract_table_structure(
                                            processed_image, region
                                        )
                                        extra_metadata[region_index] = dataclasses.asdict(
                                            table_structure
                                        )
                                    except Exception as exc:  # noqa: BLE001 - one table failing must not abort the page
                                        logger.warning(
                                            "document_intelligence_table_extraction_failed",
                                            page_number=index,
                                            region_index=region_index,
                                            error=str(exc),
                                        )

                            await document_region_service.persist_regions(
                                institution_id,
                                regions,
                                answer_script_page_id=page.id,
                                crop_storage_keys=crop_storage_keys,
                                extra_metadata=extra_metadata,
                                created_by=script.uploaded_by,
                            )
                            await session.commit()
                    except Exception as exc:  # noqa: BLE001 - layout detection is optional; OCR proceeds regardless
                        logger.warning(
                            "document_intelligence_layout_detection_failed",
                            page_number=index,
                            error=str(exc),
                        )

                pages.append((page, processed_image, blank))

            # --- Stage 5: OCR Engine ---
            await transition("ocr", "ocr_running")
            adapter = get_provider_adapter(provider_code)
            page_structures = []
            # Phase 12 (Six-Provider OCR milestone): at most one fallback
            # attempt for this whole job, not per-page -- a provider that's
            # genuinely down/misconfigured stays down for every page, so
            # there's nothing to gain (and retry-storm risk to lose) from
            # re-attempting the primary provider on each subsequent page.
            fallback_attempted = False

            for page, processed_image, blank in pages:
                if blank:
                    page.status = "ocr_complete"
                    await session.commit()
                    page_structures.append(
                        build_page_structure(
                            page_number=page.page_number, normalized_text="", blocks=[]
                        )
                    )
                    continue

                page.status = "ocr_running"
                await session.flush()
                # `extract()` needs a local file path (see `OCRProviderAdapter`'s
                # docstring) -- write the already-preprocessed bytes to a temp file.
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(encode_image_to_bytes(processed_image))
                    tmp_path = tmp.name

                if ensemble_enabled:
                    # --- Ensemble Mode (Six-Provider OCR milestone) ---
                    # Completely separate code path from the single-provider
                    # branch below -- opt-in only, so an institution that
                    # never touches `is_ensemble_enabled` is running the
                    # exact, unmodified pre-Ensemble-Mode pipeline.
                    try:
                        ensemble_run = run_ensemble(
                            tmp_path, ensemble_provider_codes, language=_DEFAULT_LANGUAGE
                        )
                    finally:
                        Path(tmp_path).unlink(missing_ok=True)

                    fusion = ensemble_run.fusion
                    assert fusion.page_result is not None
                    ocr_result = await result_service.create_with_hierarchy(
                        institution_id,
                        page.id,
                        job.id,
                        fusion.page_result,
                        created_by=script.uploaded_by,
                        provider_version="ensemble",
                        processing_time_ms=sum(
                            c.processing_time_ms or 0 for c in ensemble_run.candidates
                        ),
                        image_resolution=f"{processed_image.shape[1]}x{processed_image.shape[0]}",
                        is_ensemble_result=True,
                        contributing_provider_codes=fusion.contributing_providers,
                        disagreement_regions=[
                            {
                                "line_index": region.line_index,
                                "candidates": region.candidates,
                                "chosen_provider": region.chosen_provider,
                                "similarity": region.similarity,
                            }
                            for region in fusion.disagreement_regions
                        ],
                    )
                    await result_service.persist_candidates(
                        institution_id,
                        ocr_result.id,
                        ensemble_run.candidates,
                        created_by=script.uploaded_by,
                    )
                    page_result = fusion.page_result
                else:
                    try:
                        try:
                            page_result = adapter.extract(tmp_path, language=_DEFAULT_LANGUAGE)
                        except _PROVIDER_LEVEL_FAILURES as exc:
                            if fallback_attempted or provider_code == _FALLBACK_PROVIDER_CODE:
                                # Already fell back once this job, or the
                                # primary provider *was* the fallback target --
                                # nothing left to fall back to; let it fail and
                                # surface via Celery's own retry/failure path.
                                raise
                            fallback_attempted = True
                            fallback_query = select(OCRProvider).where(
                                OCRProvider.code == _FALLBACK_PROVIDER_CODE
                            )
                            fallback_provider = (
                                (await session.execute(fallback_query)).scalars().first()
                            )
                            if fallback_provider is None:
                                # The fallback target itself isn't registered in
                                # this deployment's catalog -- nothing safe to
                                # fall back to, so the original failure must
                                # surface rather than crash on a None attribute.
                                raise
                            logger.warning(
                                "ocr_provider_fallback",
                                answer_script_id=answer_script_id,
                                requested_provider=provider_code,
                                fallback_provider=_FALLBACK_PROVIDER_CODE,
                                reason=str(exc),
                            )
                            job.requested_ocr_provider_id = job.ocr_provider_id
                            job.ocr_provider_id = fallback_provider.id
                            job.fallback_reason = str(exc)[:2000]
                            await session.commit()
                            provider_code = _FALLBACK_PROVIDER_CODE
                            adapter = get_provider_adapter(provider_code)
                            page_result = adapter.extract(tmp_path, language=_DEFAULT_LANGUAGE)
                    finally:
                        Path(tmp_path).unlink(missing_ok=True)

                    processing_time_seconds = adapter.processing_time()
                    ocr_result = await result_service.create_with_hierarchy(
                        institution_id,
                        page.id,
                        job.id,
                        page_result,
                        created_by=script.uploaded_by,
                        provider_version=adapter.provider_version(),
                        processing_time_ms=(
                            int(processing_time_seconds * 1000)
                            if processing_time_seconds is not None
                            else None
                        ),
                        image_resolution=f"{processed_image.shape[1]}x{processed_image.shape[0]}",
                    )

                # --- Stage 7: Text Normalization ---
                ocr_result.normalized_text = normalize_text(page_result.raw_text)

                # --- Indian Multilingual Document Intelligence (Step 4.2
                # milestone) -- post-OCR script + fastText language
                # identification on the fused `raw_text` (Section 25).
                # `languagetool_code` stays `None` (falls back to
                # Step 4.1's pre-existing "en-US" default below) whenever
                # detection is disabled/fails/is low-confidence/maps to a
                # language LanguageTool doesn't support -- English pages
                # are completely unaffected either way (Section 11). ---
                languagetool_code: str | None = None
                if settings.LANGID_ENABLED:
                    try:
                        language_context = resolve_post_ocr_context(
                            ocr_result.raw_text, detector=_language_detector
                        )
                        ocr_result.multilingual_metadata = language_context.to_dict()
                        if language_context.primary_language:
                            ocr_result.language = LANGUAGE_NAME_TO_OCR_CODE.get(
                                language_context.primary_language, ocr_result.language
                            )
                            languagetool_code = LANGUAGE_NAME_TO_LANGUAGETOOL_CODE.get(
                                language_context.primary_language
                            )
                    except Exception as exc:  # noqa: BLE001 - language ID is optional; OCR proceeds regardless
                        logger.warning(
                            "multilingual_context_resolution_failed",
                            page_number=page.page_number,
                            error=str(exc),
                        )

                # --- Language Quality Intelligence (Step 4.1 milestone) ---
                # Operates on `raw_text`, not `normalized_text` -- its line
                # boundaries (`"\n".join(...)`) match `disagreement_regions`'
                # `line_index` exactly, which `normalize_text()`'s hyphen-
                # rejoining/blank-line-collapse would otherwise disturb (see
                # `language_quality.py`'s module docstring). Never fatal to
                # the page: a disabled/unavailable/timed-out/crashed analyzer
                # degrades to no language evidence, OCR stays fully usable.
                # `language=languagetool_code or "en-US"` preserves the
                # exact pre-Step-4.2 default for every page where Step
                # 4.2's detector didn't resolve a LanguageTool-supported
                # language (Section 13: unsupported languages get
                # LanguageTool's own honest `UNSUPPORTED_LANGUAGE` status,
                # never routed through English grammar analysis).
                if settings.LANGUAGE_QUALITY_ENABLED:
                    try:
                        all_ocr_lines = [
                            line for block in page_result.blocks for line in block.lines
                        ]
                        disagreement_line_indices = {
                            int(region["line_index"])
                            for region in (ocr_result.disagreement_regions or [])
                        }
                        language_evidence = analyze_language_quality(
                            ocr_result.raw_text,
                            language=languagetool_code or "en-US",
                            ocr_lines=all_ocr_lines,
                            disagreement_line_indices=disagreement_line_indices,
                        )
                        ocr_result.language_quality_metadata = language_evidence.to_dict()
                    except Exception as exc:  # noqa: BLE001 - language analysis is optional; OCR proceeds regardless
                        logger.warning(
                            "language_quality_analysis_failed",
                            page_number=page.page_number,
                            error=str(exc),
                        )

                page.status = "ocr_complete"
                await session.commit()

                blocks, lines, words = await result_service.get_hierarchy(
                    institution_id, ocr_result.id
                )
                page_structures.append(
                    _serialize_page_structure(
                        page.page_number, ocr_result.normalized_text, blocks, lines, words
                    )
                )

            job.status = "completed"
            await session.commit()

            # --- Stage 6/8: Document Structure + Structured Output ---
            await transition("structuring", "structuring")
            script.structured_content = build_structured_content(page_structures)
            script.status = "completed"
            await session.flush()
            await history_service.record(
                institution_id,
                script.id,
                stage="completed",
                from_status="structuring",
                to_status="completed",
            )
            await session.commit()

        except Exception as exc:
            await session.rollback()
            failed_script = await session.get(AnswerScript, script_id)
            if failed_script is not None:
                failed_script.status = "failed"
                failed_script.failure_reason = str(exc)[:2000]
                await history_service.record(
                    institution_id,
                    failed_script.id,
                    stage="failed",
                    to_status="failed",
                    error_detail=str(exc)[:2000],
                )
                await session.commit()
            raise
