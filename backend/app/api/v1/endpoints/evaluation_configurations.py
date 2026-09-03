"""EvaluationConfiguration management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.evaluation_configuration import EvaluationConfiguration
from app.schemas.evaluation_configuration import (
    EvaluationConfigurationCreate,
    EvaluationConfigurationRead,
    EvaluationConfigurationUpdate,
)
from app.schemas.pagination import Page, PageParams
from app.services.evaluation_configuration_service import EvaluationConfigurationService

router = APIRouter(prefix="/evaluation-configurations", tags=["Evaluation Configurations"])


def _to_read(entity: EvaluationConfiguration) -> EvaluationConfigurationRead:
    return EvaluationConfigurationRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[EvaluationConfigurationRead],
    dependencies=[Depends(require_permissions(PermissionCode.EVALUATION_CONFIGURATIONS_READ))],
)
async def list_evaluation_configurations(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[EvaluationConfigurationRead]:
    service = EvaluationConfigurationService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[EvaluationConfigurationRead],
    dependencies=[Depends(require_permissions(PermissionCode.EVALUATION_CONFIGURATIONS_DELETE))],
)
async def list_deleted_evaluation_configurations(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[EvaluationConfigurationRead]:
    service = EvaluationConfigurationService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.EVALUATION_CONFIGURATIONS_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_evaluation_configurations() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.EVALUATION_CONFIGURATIONS_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_evaluation_configurations() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.EVALUATION_CONFIGURATIONS_CREATE))],
    summary="Bulk-create evaluation configurations, collecting per-item errors instead of aborting",
)
async def bulk_create_evaluation_configurations(
    body: list[EvaluationConfigurationCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, object]:
    service = EvaluationConfigurationService(db)
    created = 0
    errors: list[dict[str, object]] = []
    for index, item in enumerate(body):
        try:
            await service.create(institution_id, item, created_by=current_user.id)
            created += 1
        except (ConflictError, NotFoundError, ValidationAppError) as exc:
            errors.append(
                {"index": index, "assessment_id": str(item.assessment_id), "error": exc.message}
            )
    await db.commit()
    return {"created": created, "errors": errors}


@router.post(
    "",
    response_model=EvaluationConfigurationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.EVALUATION_CONFIGURATIONS_CREATE))],
)
async def create_evaluation_configuration(
    body: EvaluationConfigurationCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> EvaluationConfigurationRead:
    service = EvaluationConfigurationService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=EvaluationConfigurationRead,
    dependencies=[Depends(require_permissions(PermissionCode.EVALUATION_CONFIGURATIONS_READ))],
)
async def get_evaluation_configuration(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> EvaluationConfigurationRead:
    service = EvaluationConfigurationService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=EvaluationConfigurationRead,
    dependencies=[Depends(require_permissions(PermissionCode.EVALUATION_CONFIGURATIONS_UPDATE))],
)
async def update_evaluation_configuration(
    entity_id: uuid.UUID,
    body: EvaluationConfigurationUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> EvaluationConfigurationRead:
    service = EvaluationConfigurationService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.EVALUATION_CONFIGURATIONS_DELETE))],
)
async def delete_evaluation_configuration(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = EvaluationConfigurationService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=EvaluationConfigurationRead,
    dependencies=[Depends(require_permissions(PermissionCode.EVALUATION_CONFIGURATIONS_DELETE))],
)
async def restore_evaluation_configuration(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> EvaluationConfigurationRead:
    service = EvaluationConfigurationService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
