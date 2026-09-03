"""Semester management endpoints."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import AppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.semester import Semester
from app.schemas.pagination import Page, PageParams
from app.schemas.semester import SemesterCreate, SemesterRead, SemesterUpdate
from app.services.semester_service import SemesterService

router = APIRouter(prefix="/semesters", tags=["Semesters"])


def _to_read(entity: Semester) -> SemesterRead:
    return SemesterRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[SemesterRead],
    dependencies=[Depends(require_permissions(PermissionCode.SEMESTERS_READ))],
)
async def list_semesters(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[SemesterRead]:
    service = SemesterService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[SemesterRead],
    dependencies=[Depends(require_permissions(PermissionCode.SEMESTERS_DELETE))],
)
async def list_deleted_semesters(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[SemesterRead]:
    service = SemesterService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.SEMESTERS_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_semesters() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.SEMESTERS_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_semesters() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.SEMESTERS_CREATE))],
    summary="Bulk-create semesters",
)
async def bulk_create_semesters(
    body: list[SemesterCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, Any]:
    service = SemesterService(db)
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
    response_model=SemesterRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.SEMESTERS_CREATE))],
)
async def create_semester(
    body: SemesterCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> SemesterRead:
    service = SemesterService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=SemesterRead,
    dependencies=[Depends(require_permissions(PermissionCode.SEMESTERS_READ))],
)
async def get_semester(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> SemesterRead:
    service = SemesterService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=SemesterRead,
    dependencies=[Depends(require_permissions(PermissionCode.SEMESTERS_UPDATE))],
)
async def update_semester(
    entity_id: uuid.UUID,
    body: SemesterUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> SemesterRead:
    service = SemesterService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.SEMESTERS_DELETE))],
)
async def delete_semester(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = SemesterService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=SemesterRead,
    dependencies=[Depends(require_permissions(PermissionCode.SEMESTERS_DELETE))],
)
async def restore_semester(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> SemesterRead:
    service = SemesterService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
