"""Rubric management endpoints."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import AppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.rubric import Rubric
from app.schemas.pagination import Page, PageParams
from app.schemas.rubric import RubricCreate, RubricRead, RubricUpdate
from app.services.rubric_service import RubricService

router = APIRouter(prefix="/rubrics", tags=["Rubrics"])


def _to_read(entity: Rubric) -> RubricRead:
    return RubricRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[RubricRead],
    dependencies=[Depends(require_permissions(PermissionCode.RUBRICS_READ))],
)
async def list_rubrics(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[RubricRead]:
    service = RubricService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[RubricRead],
    dependencies=[Depends(require_permissions(PermissionCode.RUBRICS_DELETE))],
)
async def list_deleted_rubrics(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[RubricRead]:
    service = RubricService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.RUBRICS_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_rubrics() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.RUBRICS_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_rubrics() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.RUBRICS_CREATE))],
    summary="Bulk-create rubrics, collecting per-item errors instead of aborting the batch",
)
async def bulk_create_rubrics(
    body: list[RubricCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, Any]:
    service = RubricService(db)
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
    response_model=RubricRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.RUBRICS_CREATE))],
)
async def create_rubric(
    body: RubricCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> RubricRead:
    service = RubricService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=RubricRead,
    dependencies=[Depends(require_permissions(PermissionCode.RUBRICS_READ))],
)
async def get_rubric(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> RubricRead:
    service = RubricService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=RubricRead,
    dependencies=[Depends(require_permissions(PermissionCode.RUBRICS_UPDATE))],
)
async def update_rubric(
    entity_id: uuid.UUID,
    body: RubricUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> RubricRead:
    service = RubricService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.RUBRICS_DELETE))],
)
async def delete_rubric(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = RubricService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=RubricRead,
    dependencies=[Depends(require_permissions(PermissionCode.RUBRICS_DELETE))],
)
async def restore_rubric(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> RubricRead:
    service = RubricService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
