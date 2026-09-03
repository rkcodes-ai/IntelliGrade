"""AcademicYear management endpoints."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import AppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.academic_year import AcademicYear
from app.schemas.academic_year import AcademicYearCreate, AcademicYearRead, AcademicYearUpdate
from app.schemas.pagination import Page, PageParams
from app.services.academic_year_service import AcademicYearService

router = APIRouter(prefix="/academic-years", tags=["Academic Years"])


def _to_read(entity: AcademicYear) -> AcademicYearRead:
    return AcademicYearRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[AcademicYearRead],
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_YEARS_READ))],
)
async def list_academic_years(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AcademicYearRead]:
    service = AcademicYearService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[AcademicYearRead],
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_YEARS_DELETE))],
)
async def list_deleted_academic_years(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AcademicYearRead]:
    service = AcademicYearService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_YEARS_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_academic_years() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_YEARS_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_academic_years() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_YEARS_CREATE))],
    summary="Bulk-create academic years",
)
async def bulk_create_academic_years(
    body: list[AcademicYearCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, Any]:
    service = AcademicYearService(db)
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
    response_model=AcademicYearRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_YEARS_CREATE))],
)
async def create_academic_year(
    body: AcademicYearCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AcademicYearRead:
    service = AcademicYearService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=AcademicYearRead,
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_YEARS_READ))],
)
async def get_academic_year(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> AcademicYearRead:
    service = AcademicYearService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=AcademicYearRead,
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_YEARS_UPDATE))],
)
async def update_academic_year(
    entity_id: uuid.UUID,
    body: AcademicYearUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AcademicYearRead:
    service = AcademicYearService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_YEARS_DELETE))],
)
async def delete_academic_year(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = AcademicYearService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=AcademicYearRead,
    dependencies=[Depends(require_permissions(PermissionCode.ACADEMIC_YEARS_DELETE))],
)
async def restore_academic_year(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AcademicYearRead:
    service = AcademicYearService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
