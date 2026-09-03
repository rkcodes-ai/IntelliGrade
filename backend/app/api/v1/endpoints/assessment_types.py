"""AssessmentType management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.assessment_type import AssessmentType
from app.schemas.assessment_type import (
    AssessmentTypeCreate,
    AssessmentTypeRead,
    AssessmentTypeUpdate,
)
from app.schemas.pagination import Page, PageParams
from app.services.assessment_type_service import AssessmentTypeService

router = APIRouter(prefix="/assessment-types", tags=["Assessment Types"])


def _to_read(entity: AssessmentType) -> AssessmentTypeRead:
    return AssessmentTypeRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[AssessmentTypeRead],
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_TYPES_READ))],
)
async def list_assessment_types(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AssessmentTypeRead]:
    service = AssessmentTypeService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[AssessmentTypeRead],
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_TYPES_DELETE))],
)
async def list_deleted_assessment_types(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AssessmentTypeRead]:
    service = AssessmentTypeService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_TYPES_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_assessment_types() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_TYPES_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_assessment_types() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_TYPES_CREATE))],
    summary="Bulk-create assessment types, collecting per-item errors instead of aborting",
)
async def bulk_create_assessment_types(
    body: list[AssessmentTypeCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, object]:
    service = AssessmentTypeService(db)
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
    response_model=AssessmentTypeRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_TYPES_CREATE))],
)
async def create_assessment_type(
    body: AssessmentTypeCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AssessmentTypeRead:
    service = AssessmentTypeService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=AssessmentTypeRead,
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_TYPES_READ))],
)
async def get_assessment_type(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> AssessmentTypeRead:
    service = AssessmentTypeService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=AssessmentTypeRead,
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_TYPES_UPDATE))],
)
async def update_assessment_type(
    entity_id: uuid.UUID,
    body: AssessmentTypeUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AssessmentTypeRead:
    service = AssessmentTypeService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_TYPES_DELETE))],
)
async def delete_assessment_type(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = AssessmentTypeService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=AssessmentTypeRead,
    dependencies=[Depends(require_permissions(PermissionCode.ASSESSMENT_TYPES_DELETE))],
)
async def restore_assessment_type(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AssessmentTypeRead:
    service = AssessmentTypeService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
