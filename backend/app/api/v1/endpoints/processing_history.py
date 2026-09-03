"""
Processing history browsing endpoints (read-only).

Fully read-only, append-only: only `GET ""`/`GET "/{id}"` are exposed here
-- no `POST`/`PATCH`/`DELETE` route. Rows are inserted internally by
pipeline/task code via `ProcessingHistoryService.record()` (see
`app/services/processing_history_service.py`), never through this router.
`GET ""` additionally supports filtering by `answer_script_id` via
`ProcessingHistoryListParams`.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.deps import DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.processing_history import ProcessingHistory
from app.schemas.pagination import Page
from app.schemas.processing_history import ProcessingHistoryListParams, ProcessingHistoryRead
from app.services.processing_history_service import ProcessingHistoryService

router = APIRouter(prefix="/processing-history", tags=["Processing History"])


def _to_read(entity: ProcessingHistory) -> ProcessingHistoryRead:
    return ProcessingHistoryRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[ProcessingHistoryRead],
    dependencies=[Depends(require_permissions(PermissionCode.PROCESSING_HISTORY_READ))],
)
async def list_processing_history(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    params: Annotated[ProcessingHistoryListParams, Depends()],
) -> Page[ProcessingHistoryRead]:
    service = ProcessingHistoryService(db)
    extra_filters: tuple[Any, ...] = ()
    if params.answer_script_id is not None:
        extra_filters = (ProcessingHistory.answer_script_id == params.answer_script_id,)
    items, total = await service.list_paginated(institution_id, params, extra_filters=extra_filters)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/{entity_id}",
    response_model=ProcessingHistoryRead,
    dependencies=[Depends(require_permissions(PermissionCode.PROCESSING_HISTORY_READ))],
)
async def get_processing_history(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> ProcessingHistoryRead:
    service = ProcessingHistoryService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)
