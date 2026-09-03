"""OCRResultService — persists/reads the OCR output hierarchy for one AnswerScriptPage."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.models.ocr_block import OCRBlock
from app.models.ocr_line import OCRLine
from app.models.ocr_provider_candidate import OCRProviderCandidate
from app.models.ocr_result import OCRResult
from app.models.ocr_word import OCRWord
from app.repositories.ocr_block_repository import OCRBlockRepository
from app.repositories.ocr_line_repository import OCRLineRepository
from app.repositories.ocr_result_repository import OCRResultRepository
from app.repositories.ocr_word_repository import OCRWordRepository
from app.services.audit_service import AuditService
from app.services.ocr.base import OCRLineResult, OCRPageResult
from app.services.ocr.ensemble import EnsembleCandidateOutcome
from app.services.tenant_service import TenantScopedService


def _to_decimal(value: float) -> Decimal:
    """`Decimal(str(value))`, not `Decimal(value)` -- avoids binary-float
    imprecision (e.g. `Decimal(0.1)` != `Decimal("0.1")`) when persisting
    the `float` confidence/rotation values `OCRProviderAdapter.extract()`
    returns into `Numeric(5, 2)` columns."""
    return Decimal(str(value))


def _serialize_page_result(page_result: OCRPageResult) -> dict[str, Any]:
    """Full block->line->word tree as plain JSON, for
    `OCRProviderCandidate.structured_content` -- read as one unit by the
    fusion engine/any future debugging UI, never queried piecemeal (same
    "one JSON column" reasoning as the model's own docstring)."""
    return {
        "raw_text": page_result.raw_text,
        "average_confidence": page_result.average_confidence,
        "language": page_result.language,
        "rotation_degrees": page_result.rotation_degrees,
        "blocks": [
            {
                "block_type": block.block_type,
                "reading_order": block.reading_order,
                "confidence": block.confidence,
                "bbox": {
                    "left": block.bounding_box.left,
                    "top": block.bounding_box.top,
                    "width": block.bounding_box.width,
                    "height": block.bounding_box.height,
                },
                "lines": [
                    {
                        "text": line.text,
                        "confidence": line.confidence,
                        "reading_order": line.reading_order,
                        "bbox": {
                            "left": line.bounding_box.left,
                            "top": line.bounding_box.top,
                            "width": line.bounding_box.width,
                            "height": line.bounding_box.height,
                        },
                    }
                    for line in block.lines
                ],
            }
            for block in page_result.blocks
        ],
    }


class OCRResultService(TenantScopedService[OCRResult]):
    """
    Entirely read-only from the API's perspective (`GET`-only router, see
    `app/api/v1/endpoints/ocr_results.py`); the one write path is
    `create_with_hierarchy()`, called directly by pipeline/task code (never
    through an HTTP route) once an OCR engine has finished processing a
    page.
    """

    resource_type = "ocr_result"

    def __init__(
        self,
        session: AsyncSession,
        repo: OCRResultRepository | None = None,
        *,
        block_repo: OCRBlockRepository | None = None,
        line_repo: OCRLineRepository | None = None,
        word_repo: OCRWordRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session, repo or OCRResultRepository(session), audit_service=audit_service)
        self._block_repo = block_repo or OCRBlockRepository(session)
        self._line_repo = line_repo or OCRLineRepository(session)
        self._word_repo = word_repo or OCRWordRepository(session)

    async def create_with_hierarchy(
        self,
        institution_id: uuid.UUID,
        answer_script_page_id: uuid.UUID,
        ocr_job_id: uuid.UUID,
        page_result: OCRPageResult,
        *,
        created_by: uuid.UUID | None,
        provider_version: str | None = None,
        processing_time_ms: int | None = None,
        image_resolution: str | None = None,
        raw_response_reference: str | None = None,
        is_ensemble_result: bool = False,
        contributing_provider_codes: list[str] | None = None,
        disagreement_regions: list[dict[str, Any]] | None = None,
    ) -> OCRResult:
        """
        Single entry point pipeline/task code calls to persist one page's
        entire OCR output tree (`OCRResult` -> `OCRBlock` -> `OCRLine` ->
        `OCRWord`) atomically, from the engine-agnostic `OCRPageResult`
        shape every `OCRProviderAdapter.extract()` returns (see
        `app.services.ocr.base`). Never called through an HTTP route --
        all four entities are read-only from the API's perspective.

        Bulk `session.add_all(...)` per level, flushing between levels so
        each child row can reference its parent's freshly app-side-
        generated id -- this is the one deliberate divergence from "one
        service, one entity" in this module, justified because the tree is
        always created atomically as a unit, never block-by-block.
        `normalized_text` stays `NULL` -- populated by a later Stage 7
        pipeline step, not part of this method.

        The four keyword-only `provider_version`/`processing_time_ms`/
        `image_resolution`/`raw_response_reference` params (Module 12) are
        all optional and independent of `page_result` -- callers still on
        the plain `extract()` call can pass as many or as few as they have
        readily available (see `app.tasks.ocr_tasks`).

        `is_ensemble_result`/`contributing_provider_codes`/
        `disagreement_regions` (Six-Provider OCR milestone) default to
        `False`/`None`/`None` -- every pre-Ensemble-Mode call site is
        unaffected. Pass them (and call `persist_candidates()` right
        after) only when `page_result` came from
        `app.services.ocr.fusion.fuse_page_candidates`, not a single
        provider's direct `extract()`.

        Caller must `await db.commit()` afterward -- this service never
        commits itself (see `TenantScopedService`/hard rules).
        """
        result = OCRResult(
            institution_id=institution_id,
            answer_script_page_id=answer_script_page_id,
            ocr_job_id=ocr_job_id,
            raw_text=page_result.raw_text,
            normalized_text=None,
            average_confidence=_to_decimal(page_result.average_confidence),
            language=page_result.language,
            rotation_degrees=_to_decimal(page_result.rotation_degrees),
            reading_order_verified=False,
            provider_version=provider_version,
            processing_time_ms=processing_time_ms,
            image_resolution=image_resolution,
            raw_response_reference=raw_response_reference,
            is_ensemble_result=is_ensemble_result,
            contributing_provider_codes=contributing_provider_codes,
            disagreement_regions=disagreement_regions,
            created_by=created_by,
        )
        result = await self.repo.add(result)

        blocks = [
            OCRBlock(
                institution_id=institution_id,
                ocr_result_id=result.id,
                block_type=block.block_type,
                reading_order=block.reading_order,
                bbox_left=block.bounding_box.left,
                bbox_top=block.bounding_box.top,
                bbox_width=block.bounding_box.width,
                bbox_height=block.bounding_box.height,
                confidence=_to_decimal(block.confidence),
                created_by=created_by,
            )
            for block in page_result.blocks
        ]
        if blocks:
            self.session.add_all(blocks)
            await self.session.flush()

        # Pair each source `OCRLineResult` with the `OCRBlock` row it
        # belongs to (now carrying a real id, post-flush) so words can
        # later be attached to the right freshly-flushed `OCRLine.id`
        # without re-deriving the block->line->word nesting a second time.
        line_pairs: list[tuple[OCRLineResult, OCRLine]] = [
            (
                line,
                OCRLine(
                    institution_id=institution_id,
                    ocr_block_id=db_block.id,
                    text=line.text,
                    reading_order=line.reading_order,
                    bbox_left=line.bounding_box.left,
                    bbox_top=line.bounding_box.top,
                    bbox_width=line.bounding_box.width,
                    bbox_height=line.bounding_box.height,
                    confidence=_to_decimal(line.confidence),
                    created_by=created_by,
                ),
            )
            for src_block, db_block in zip(page_result.blocks, blocks, strict=True)
            for line in src_block.lines
        ]
        if line_pairs:
            self.session.add_all(db_line for _, db_line in line_pairs)
            await self.session.flush()

        words = [
            OCRWord(
                institution_id=institution_id,
                ocr_line_id=db_line.id,
                text=word.text,
                reading_order=word.reading_order,
                bbox_left=word.bounding_box.left,
                bbox_top=word.bounding_box.top,
                bbox_width=word.bounding_box.width,
                bbox_height=word.bounding_box.height,
                confidence=_to_decimal(word.confidence),
                created_by=created_by,
            )
            for src_line, db_line in line_pairs
            for word in src_line.words
        ]
        if words:
            self.session.add_all(words)
            await self.session.flush()

        await self._log_audit(AuditAction.OCR_PROCESSING_COMPLETED, created_by, result.id)
        return result

    async def persist_candidates(
        self,
        institution_id: uuid.UUID,
        ocr_result_id: uuid.UUID,
        outcomes: list[EnsembleCandidateOutcome],
        *,
        created_by: uuid.UUID | None,
    ) -> list[OCRProviderCandidate]:
        """Persist every ensemble candidate (successful *and* failed) for
        one `OCRResult` -- the raw, per-provider record the milestone's
        "preserve raw OCR results, never discard after fusion" requirement
        exists for. Caller must `await db.commit()` afterward, same
        convention as `create_with_hierarchy()`."""
        rows = [
            OCRProviderCandidate(
                institution_id=institution_id,
                ocr_result_id=ocr_result_id,
                provider_code=outcome.provider_code,
                status=outcome.status,
                raw_text=outcome.result.raw_text if outcome.result is not None else None,
                confidence=(
                    _to_decimal(outcome.result.average_confidence)
                    if outcome.result is not None
                    else None
                ),
                structured_content=_serialize_page_result(outcome.result)
                if outcome.result is not None
                else None,
                error_message=outcome.error_message,
                processing_time_ms=outcome.processing_time_ms,
                created_by=created_by,
            )
            for outcome in outcomes
        ]
        if rows:
            self.session.add_all(rows)
            await self.session.flush()
        return rows

    async def get_hierarchy(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID
    ) -> tuple[list[OCRBlock], list[OCRLine], list[OCRWord]]:
        """
        Validates the `OCRResult` exists for this institution (404 if not),
        then returns every descendant `OCRBlock`/`OCRLine`/`OCRWord` as
        three flat, ordered lists -- three queries total, not N+1 -- for
        `GET /ocr-results/{id}/blocks` to group into a nested tree.
        """
        await self.get_by_id(institution_id, entity_id)
        blocks = await self._block_repo.list_by_result(institution_id, entity_id)
        block_ids = [block.id for block in blocks]
        lines = await self._line_repo.list_by_blocks(institution_id, block_ids)
        line_ids = [line.id for line in lines]
        words = await self._word_repo.list_by_lines(institution_id, line_ids)
        return blocks, lines, words
