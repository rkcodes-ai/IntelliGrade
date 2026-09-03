"""Class schedule management endpoints."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import AppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.class_schedule import ClassSchedule
from app.schemas.class_schedule import ClassScheduleCreate, ClassScheduleRead, ClassScheduleUpdate
from app.schemas.pagination import Page, PageParams
from app.services.class_schedule_service import ClassScheduleService

router = APIRouter(prefix="/class-schedules", tags=["Class Schedules"])


def _to_read(entity: ClassSchedule) -> ClassScheduleRead:
    return ClassScheduleRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[ClassScheduleRead],
    dependencies=[Depends(require_permissions(PermissionCode.CLASS_SCHEDULES_READ))],
)
async def list_class_schedules(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[ClassScheduleRead]:
    service = ClassScheduleService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[ClassScheduleRead],
    dependencies=[Depends(require_permissions(PermissionCode.CLASS_SCHEDULES_DELETE))],
)
async def list_deleted_class_schedules(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[ClassScheduleRead]:
    service = ClassScheduleService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.CLASS_SCHEDULES_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_class_schedules() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.CLASS_SCHEDULES_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_class_schedules() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.CLASS_SCHEDULES_CREATE))],
    summary="Bulk-create class schedules",
)
async def bulk_create_class_schedules(
    body: list[ClassScheduleCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, Any]:
    service = ClassScheduleService(db)
    created = 0
    errors: list[dict[str, Any]] = []
    for index, item in enumerate(body):
        try:
            await service.create(institution_id, item, created_by=current_user.id)
            created += 1
        except AppError as exc:
            errors.append({"index": index, "message": exc.message})
    await db.commit()
    return {"created": created, "errors": errors}


@router.post(
    "",
    response_model=ClassScheduleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.CLASS_SCHEDULES_CREATE))],
)
async def create_class_schedule(
    body: ClassScheduleCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ClassScheduleRead:
    service = ClassScheduleService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=ClassScheduleRead,
    dependencies=[Depends(require_permissions(PermissionCode.CLASS_SCHEDULES_READ))],
)
async def get_class_schedule(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> ClassScheduleRead:
    service = ClassScheduleService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=ClassScheduleRead,
    dependencies=[Depends(require_permissions(PermissionCode.CLASS_SCHEDULES_UPDATE))],
)
async def update_class_schedule(
    entity_id: uuid.UUID,
    body: ClassScheduleUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ClassScheduleRead:
    service = ClassScheduleService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.CLASS_SCHEDULES_DELETE))],
)
async def delete_class_schedule(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = ClassScheduleService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=ClassScheduleRead,
    dependencies=[Depends(require_permissions(PermissionCode.CLASS_SCHEDULES_DELETE))],
)
async def restore_class_schedule(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ClassScheduleRead:
    service = ClassScheduleService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
