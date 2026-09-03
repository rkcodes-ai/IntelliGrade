"""
OCR output hierarchy browsing endpoints (read-only).

Covers all four entities of the `OCRResult 1-* OCRBlock 1-* OCRLine 1-*
OCRWord` hierarchy (see ADR-029) behind a single `OCR_RESULTS_READ`
permission -- per this module's spec, no separate permission code exists
per sub-entity. Only `GET ""`/`GET "/{id}"` per entity, plus one nested
convenience route (`GET /ocr-results/{id}/blocks`) that assembles the full
block/line/word tree for one page's OCR output as nested JSON -- the route
the frontend's OCR Text Viewer / bounding-box overlay actually uses. Rows
are inserted exclusively by `OCRResultService.create_with_hierarchy()`
(see `app/services/ocr_result_service.py`), never through this router.
"""

import uuid
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.ocr_block import OCRBlock
from app.models.ocr_line import OCRLine
from app.models.ocr_result import OCRResult
from app.models.ocr_word import OCRWord
from app.schemas.ocr_block import OCRBlockRead, OCRBlockWithChildren
from app.schemas.ocr_line import OCRLineRead, OCRLineWithChildren
from app.schemas.ocr_result import OCRResultRead
from app.schemas.ocr_word import OCRWordRead
from app.schemas.pagination import Page, PageParams
from app.services.ocr_block_service import OCRBlockService
from app.services.ocr_line_service import OCRLineService
from app.services.ocr_result_service import OCRResultService
from app.services.ocr_word_service import OCRWordService

results_router = APIRouter(prefix="/ocr-results", tags=["OCR Results"])
blocks_router = APIRouter(prefix="/ocr-blocks", tags=["OCR Blocks"])
lines_router = APIRouter(prefix="/ocr-lines", tags=["OCR Lines"])
words_router = APIRouter(prefix="/ocr-words", tags=["OCR Words"])


def _result_to_read(entity: OCRResult) -> OCRResultRead:
    return OCRResultRead.model_validate(entity)


def _block_to_read(entity: OCRBlock) -> OCRBlockRead:
    return OCRBlockRead.model_validate(entity)


def _line_to_read(entity: OCRLine) -> OCRLineRead:
    return OCRLineRead.model_validate(entity)


def _word_to_read(entity: OCRWord) -> OCRWordRead:
    return OCRWordRead.model_validate(entity)


# --- OCRResult ---------------------------------------------------------


@results_router.get(
    "",
    response_model=Page[OCRResultRead],
    dependencies=[Depends(require_permissions(PermissionCode.OCR_RESULTS_READ))],
)
async def list_ocr_results(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[OCRResultRead]:
    service = OCRResultService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_result_to_read(i) for i in items], total=total, params=params)


@results_router.get(
    "/{entity_id}",
    response_model=OCRResultRead,
    dependencies=[Depends(require_permissions(PermissionCode.OCR_RESULTS_READ))],
)
async def get_ocr_result(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> OCRResultRead:
    service = OCRResultService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _result_to_read(entity)


@results_router.get(
    "/{entity_id}/blocks",
    response_model=list[OCRBlockWithChildren],
    dependencies=[Depends(require_permissions(PermissionCode.OCR_RESULTS_READ))],
)
async def get_ocr_result_blocks(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> list[OCRBlockWithChildren]:
    """Full block -> line -> word tree for one `OCRResult`, as nested JSON."""
    service = OCRResultService(db)
    blocks, lines, words = await service.get_hierarchy(institution_id, entity_id)

    words_by_line: dict[uuid.UUID, list[OCRWordRead]] = defaultdict(list)
    for word in words:
        words_by_line[word.ocr_line_id].append(_word_to_read(word))

    lines_by_block: dict[uuid.UUID, list[OCRLineWithChildren]] = defaultdict(list)
    for line in lines:
        lines_by_block[line.ocr_block_id].append(
            OCRLineWithChildren(**_line_to_read(line).model_dump(), words=words_by_line[line.id])
        )

    return [
        OCRBlockWithChildren(**_block_to_read(block).model_dump(), lines=lines_by_block[block.id])
        for block in blocks
    ]


# --- OCRBlock ------------------------------------------------------------


@blocks_router.get(
    "",
    response_model=Page[OCRBlockRead],
    dependencies=[Depends(require_permissions(PermissionCode.OCR_RESULTS_READ))],
)
async def list_ocr_blocks(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[OCRBlockRead]:
    service = OCRBlockService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_block_to_read(i) for i in items], total=total, params=params)


@blocks_router.get(
    "/{entity_id}",
    response_model=OCRBlockRead,
    dependencies=[Depends(require_permissions(PermissionCode.OCR_RESULTS_READ))],
)
async def get_ocr_block(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> OCRBlockRead:
    service = OCRBlockService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _block_to_read(entity)


# --- OCRLine ---------------------------------------------------------------


@lines_router.get(
    "",
    response_model=Page[OCRLineRead],
    dependencies=[Depends(require_permissions(PermissionCode.OCR_RESULTS_READ))],
)
async def list_ocr_lines(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[OCRLineRead]:
    service = OCRLineService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_line_to_read(i) for i in items], total=total, params=params)


@lines_router.get(
    "/{entity_id}",
    response_model=OCRLineRead,
    dependencies=[Depends(require_permissions(PermissionCode.OCR_RESULTS_READ))],
)
async def get_ocr_line(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> OCRLineRead:
    service = OCRLineService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _line_to_read(entity)


# --- OCRWord ---------------------------------------------------------------


@words_router.get(
    "",
    response_model=Page[OCRWordRead],
    dependencies=[Depends(require_permissions(PermissionCode.OCR_RESULTS_READ))],
)
async def list_ocr_words(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[OCRWordRead]:
    service = OCRWordService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_word_to_read(i) for i in items], total=total, params=params)


@words_router.get(
    "/{entity_id}",
    response_model=OCRWordRead,
    dependencies=[Depends(require_permissions(PermissionCode.OCR_RESULTS_READ))],
)
async def get_ocr_word(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> OCRWordRead:
    service = OCRWordService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _word_to_read(entity)


router = APIRouter()
router.include_router(results_router)
router.include_router(blocks_router)
router.include_router(lines_router)
router.include_router(words_router)
