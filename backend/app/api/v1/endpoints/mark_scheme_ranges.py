"""
MarkSchemeRange management endpoints.

Rows are written internally by the ingestion pipeline
(`app.tasks.official_document_tasks`), never through this router — there is
no `POST ""`. `GET ""` supports filtering to one parent document via
`?document_id=`. `GET "/expand"` expands every range for a document into a
per-question maximum-marks map via `MarkSchemeRangeService.expand_for_document`.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.mark_scheme_range import MarkSchemeRange
from app.schemas.mark_scheme_range import (
    MarkSchemeExpansionResponse,
    MarkSchemeRangeRead,
    MarkSchemeRangeUpdate,
)
from app.schemas.pagination import Page, PageParams
from app.services.mark_scheme_range_service import MarkSchemeRangeService

router = APIRouter(prefix="/mark-scheme-ranges", tags=["Mark Scheme Ranges"])


def _to_read(entity: MarkSchemeRange) -> MarkSchemeRangeRead:
    return MarkSchemeRangeRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[MarkSchemeRangeRead],
    dependencies=[Depends(require_permissions(PermissionCode.MARK_SCHEME_RANGES_READ))],
)
async def list_mark_scheme_ranges(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    params: Annotated[PageParams, Depends()],
    document_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[MarkSchemeRangeRead]:
    service = MarkSchemeRangeService(db)
    extra_filters: tuple[Any, ...] = ()
    if document_id is not None:
        extra_filters = (MarkSchemeRange.document_id == document_id,)
    items, total = await service.list_paginated(institution_id, params, extra_filters=extra_filters)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/expand",
    response_model=MarkSchemeExpansionResponse,
    dependencies=[Depends(require_permissions(PermissionCode.MARK_SCHEME_RANGES_READ))],
)
async def expand_mark_scheme_ranges_for_document(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    document_id: Annotated[uuid.UUID, Query()],
) -> MarkSchemeExpansionResponse:
    service = MarkSchemeRangeService(db)
    result = await service.expand_for_document(institution_id, document_id)
    return MarkSchemeExpansionResponse(
        marks_by_question=result.marks_by_question, warnings=result.warnings
    )


@router.get(
    "/{entity_id}",
    response_model=MarkSchemeRangeRead,
    dependencies=[Depends(require_permissions(PermissionCode.MARK_SCHEME_RANGES_READ))],
)
async def get_mark_scheme_range(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> MarkSchemeRangeRead:
    service = MarkSchemeRangeService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=MarkSchemeRangeRead,
    dependencies=[Depends(require_permissions(PermissionCode.MARK_SCHEME_RANGES_UPDATE))],
)
async def update_mark_scheme_range(
    entity_id: uuid.UUID,
    body: MarkSchemeRangeUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> MarkSchemeRangeRead:
    service = MarkSchemeRangeService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/verify",
    response_model=MarkSchemeRangeRead,
    dependencies=[Depends(require_permissions(PermissionCode.MARK_SCHEME_RANGES_VERIFY))],
)
async def verify_mark_scheme_range(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> MarkSchemeRangeRead:
    service = MarkSchemeRangeService(db)
    entity = await service.verify(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)
