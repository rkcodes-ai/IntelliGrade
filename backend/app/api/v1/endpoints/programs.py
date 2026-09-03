"""Program management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.program import Program
from app.schemas.pagination import Page, PageParams
from app.schemas.program import ProgramCreate, ProgramRead, ProgramUpdate
from app.services.program_service import ProgramService

router = APIRouter(prefix="/programs", tags=["Programs"])


def _to_read(entity: Program) -> ProgramRead:
    return ProgramRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[ProgramRead],
    dependencies=[Depends(require_permissions(PermissionCode.PROGRAMS_READ))],
)
async def list_programs(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[ProgramRead]:
    service = ProgramService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[ProgramRead],
    dependencies=[Depends(require_permissions(PermissionCode.PROGRAMS_DELETE))],
)
async def list_deleted_programs(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[ProgramRead]:
    service = ProgramService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.PROGRAMS_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_programs() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.PROGRAMS_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_programs() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.PROGRAMS_CREATE))],
    summary="Bulk-create programs, collecting per-item errors instead of aborting the batch",
)
async def bulk_create_programs(
    body: list[ProgramCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, object]:
    service = ProgramService(db)
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
    response_model=ProgramRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.PROGRAMS_CREATE))],
)
async def create_program(
    body: ProgramCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ProgramRead:
    service = ProgramService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=ProgramRead,
    dependencies=[Depends(require_permissions(PermissionCode.PROGRAMS_READ))],
)
async def get_program(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> ProgramRead:
    service = ProgramService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=ProgramRead,
    dependencies=[Depends(require_permissions(PermissionCode.PROGRAMS_UPDATE))],
)
async def update_program(
    entity_id: uuid.UUID,
    body: ProgramUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ProgramRead:
    service = ProgramService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.PROGRAMS_DELETE))],
)
async def delete_program(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = ProgramService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=ProgramRead,
    dependencies=[Depends(require_permissions(PermissionCode.PROGRAMS_DELETE))],
)
async def restore_program(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ProgramRead:
    service = ProgramService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
