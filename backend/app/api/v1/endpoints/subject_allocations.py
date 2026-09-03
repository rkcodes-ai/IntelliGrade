"""SubjectAllocation management endpoints."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import AppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.subject_allocation import SubjectAllocation
from app.schemas.pagination import Page, PageParams
from app.schemas.subject_allocation import (
    SubjectAllocationCreate,
    SubjectAllocationRead,
    SubjectAllocationUpdate,
)
from app.services.subject_allocation_service import SubjectAllocationService

router = APIRouter(prefix="/subject-allocations", tags=["Subject Allocations"])


def _to_read(entity: SubjectAllocation) -> SubjectAllocationRead:
    return SubjectAllocationRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[SubjectAllocationRead],
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_ALLOCATIONS_READ))],
)
async def list_subject_allocations(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[SubjectAllocationRead]:
    service = SubjectAllocationService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[SubjectAllocationRead],
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_ALLOCATIONS_DELETE))],
)
async def list_deleted_subject_allocations(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[SubjectAllocationRead]:
    service = SubjectAllocationService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_ALLOCATIONS_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_subject_allocations() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_ALLOCATIONS_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_subject_allocations() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_ALLOCATIONS_CREATE))],
    summary="Bulk-create subject allocations",
)
async def bulk_create_subject_allocations(
    body: list[SubjectAllocationCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, Any]:
    service = SubjectAllocationService(db)
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
    response_model=SubjectAllocationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_ALLOCATIONS_CREATE))],
)
async def create_subject_allocation(
    body: SubjectAllocationCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> SubjectAllocationRead:
    service = SubjectAllocationService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=SubjectAllocationRead,
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_ALLOCATIONS_READ))],
)
async def get_subject_allocation(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> SubjectAllocationRead:
    service = SubjectAllocationService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=SubjectAllocationRead,
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_ALLOCATIONS_UPDATE))],
)
async def update_subject_allocation(
    entity_id: uuid.UUID,
    body: SubjectAllocationUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> SubjectAllocationRead:
    service = SubjectAllocationService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_ALLOCATIONS_DELETE))],
)
async def delete_subject_allocation(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = SubjectAllocationService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=SubjectAllocationRead,
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_ALLOCATIONS_DELETE))],
)
async def restore_subject_allocation(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> SubjectAllocationRead:
    service = SubjectAllocationService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
