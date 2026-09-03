"""
OCR job management endpoints -- system-managed execution records.

No `PATCH`/`DELETE`/restore route (mirrors `QuestionApproval`'s read-mostly
precedent, but with the two explicit action endpoints below instead of zero
writes): `POST ""` only persists a queued job row -- it does not enqueue a
Celery task itself (see `OCRJobService.create`'s docstring) -- and
`POST "/{id}/cancel"` is the only other mutation, guarded to `"queued"`/
`"running"` jobs.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.ocr_job import OCRJob
from app.schemas.ocr_job import OCRJobCreate, OCRJobRead
from app.schemas.pagination import Page, PageParams
from app.services.ocr_job_service import OCRJobService

router = APIRouter(prefix="/ocr-jobs", tags=["OCR Jobs"])


def _to_read(entity: OCRJob) -> OCRJobRead:
    return OCRJobRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[OCRJobRead],
    dependencies=[Depends(require_permissions(PermissionCode.OCR_JOBS_READ))],
)
async def list_ocr_jobs(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[OCRJobRead]:
    service = OCRJobService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "",
    response_model=OCRJobRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.OCR_JOBS_CREATE))],
)
async def create_ocr_job(
    body: OCRJobCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> OCRJobRead:
    service = OCRJobService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=OCRJobRead,
    dependencies=[Depends(require_permissions(PermissionCode.OCR_JOBS_READ))],
)
async def get_ocr_job(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> OCRJobRead:
    service = OCRJobService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.post(
    "/{entity_id}/cancel",
    response_model=OCRJobRead,
    dependencies=[Depends(require_permissions(PermissionCode.OCR_JOBS_CANCEL))],
)
async def cancel_ocr_job(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> OCRJobRead:
    service = OCRJobService(db)
    entity = await service.cancel(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)
