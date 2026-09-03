"""AssessmentStatus management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.assessment_status import AssessmentStatus
from app.schemas.assessment_status import (
    AssessmentStatusCreate,
    AssessmentStatusRead,
    AssessmentStatusUpdate,
)
from app.schemas.pagination import Page, PageParams
from app.services.assessment_status_service import AssessmentStatusService

router = APIRouter(prefix="/assessment-statuses", tags=["Assessment Statuses"])


def _to_read(entity: AssessmentStatus) -> AssessmentStatusRead:
    return AssessmentStatusRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[AssessmentStatusRead],
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_STATUSES_READ))],
)
async def list_assessment_statuses(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AssessmentStatusRead]:
    service = AssessmentStatusService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[AssessmentStatusRead],
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_STATUSES_DELETE))],
)
async def list_deleted_assessment_statuses(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AssessmentStatusRead]:
    service = AssessmentStatusService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_STATUSES_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_assessment_statuses() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_STATUSES_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_assessment_statuses() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_STATUSES_CREATE))],
    summary="Bulk-create assessment statuses, collecting per-item errors instead of aborting",
)
async def bulk_create_assessment_statuses(
    body: list[AssessmentStatusCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, object]:
    service = AssessmentStatusService(db)
    created = 0
    errors: list[dict[str, object]] = []
    for index, item in enumerate(body):
        try:
            await service.create(institution_id, item, created_by=current_user.id)
            created += 1
        except (ConflictError, NotFoundError, ValidationAppError) as exc:
            errors.append({"index": index, "code": item.code, "error": exc.message})
    await db.commit()
    return {"created": created, "errors": errors}


@router.post(
    "",
    response_model=AssessmentStatusRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_STATUSES_CREATE))],
)
async def create_assessment_status(
    body: AssessmentStatusCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AssessmentStatusRead:
    service = AssessmentStatusService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=AssessmentStatusRead,
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_STATUSES_READ))],
)
async def get_assessment_status(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> AssessmentStatusRead:
    service = AssessmentStatusService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=AssessmentStatusRead,
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_STATUSES_UPDATE))],
)
async def update_assessment_status(
    entity_id: uuid.UUID,
    body: AssessmentStatusUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AssessmentStatusRead:
    service = AssessmentStatusService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_STATUSES_DELETE))],
)
async def delete_assessment_status(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = AssessmentStatusService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=AssessmentStatusRead,
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_STATUSES_DELETE))],
)
async def restore_assessment_status(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AssessmentStatusRead:
    service = AssessmentStatusService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
