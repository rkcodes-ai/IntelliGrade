"""
UploadJob browsing endpoints (read-only) — powers the frontend's Upload
Queue / Progress Monitor. Rows are written internally by
`AnswerScriptService.upload()`, never through a client-facing `POST`
(that endpoint isn't exposed here at all — `upload_jobs:create` exists as
a permission code for a future chunked-upload flow, but the current
single-shot `POST /answer-scripts` already creates a completed `UploadJob`
row as part of its own transaction).
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.upload_job import UploadJob
from app.schemas.pagination import Page, PageParams
from app.schemas.upload_job import UploadJobRead
from app.services.upload_job_service import UploadJobService

router = APIRouter(prefix="/upload-jobs", tags=["Upload Jobs"])


def _to_read(entity: UploadJob) -> UploadJobRead:
    return UploadJobRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[UploadJobRead],
    dependencies=[Depends(require_permissions(PermissionCode.UPLOAD_JOBS_READ))],
)
async def list_upload_jobs(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    params: Annotated[PageParams, Depends()],
    answer_script_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[UploadJobRead]:
    service = UploadJobService(db)
    extra_filters: tuple[Any, ...] = ()
    if answer_script_id is not None:
        extra_filters = (UploadJob.answer_script_id == answer_script_id,)
    items, total = await service.list_paginated(institution_id, params, extra_filters=extra_filters)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/{entity_id}",
    response_model=UploadJobRead,
    dependencies=[Depends(require_permissions(PermissionCode.UPLOAD_JOBS_READ))],
)
async def get_upload_job(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> UploadJobRead:
    service = UploadJobService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)
