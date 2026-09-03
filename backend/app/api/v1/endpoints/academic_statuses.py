"""AcademicStatus management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.academic_status import AcademicStatus
from app.schemas.academic_status import (
    AcademicStatusCreate,
    AcademicStatusRead,
    AcademicStatusUpdate,
)
from app.schemas.pagination import Page, PageParams
from app.services.academic_status_service import AcademicStatusService

router = APIRouter(prefix="/academic-statuses", tags=["Academic Statuses"])


def _to_read(entity: AcademicStatus) -> AcademicStatusRead:
    return AcademicStatusRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[AcademicStatusRead],
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_STATUSES_READ))],
)
async def list_academic_statuses(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AcademicStatusRead]:
    service = AcademicStatusService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[AcademicStatusRead],
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_STATUSES_DELETE))],
)
async def list_deleted_academic_statuses(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AcademicStatusRead]:
    service = AcademicStatusService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_STATUSES_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_academic_statuses() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_STATUSES_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_academic_statuses() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_STATUSES_CREATE))],
    summary="Bulk-create academic statuses, collecting per-item errors instead of aborting",
)
async def bulk_create_academic_statuses(
    body: list[AcademicStatusCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, object]:
    service = AcademicStatusService(db)
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
    response_model=AcademicStatusRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_STATUSES_CREATE))],
)
async def create_academic_status(
    body: AcademicStatusCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AcademicStatusRead:
    service = AcademicStatusService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=AcademicStatusRead,
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_STATUSES_READ))],
)
async def get_academic_status(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> AcademicStatusRead:
    service = AcademicStatusService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=AcademicStatusRead,
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_STATUSES_UPDATE))],
)
async def update_academic_status(
    entity_id: uuid.UUID,
    body: AcademicStatusUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AcademicStatusRead:
    service = AcademicStatusService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_STATUSES_DELETE))],
)
async def delete_academic_status(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = AcademicStatusService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=AcademicStatusRead,
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_STATUSES_DELETE))],
)
async def restore_academic_status(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AcademicStatusRead:
    service = AcademicStatusService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    # See `subject_categories.restore_subject_category` for why this refresh
    # is needed (avoids a post-flush `MissingGreenlet` on `updated_at`).
    await db.refresh(entity)
    await db.commit()
    return _to_read(entity)
