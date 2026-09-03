"""AI configuration management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.ai_configuration import AIConfiguration
from app.schemas.ai_configuration import (
    AIConfigurationCreate,
    AIConfigurationRead,
    AIConfigurationUpdate,
)
from app.schemas.pagination import Page, PageParams
from app.services.ai_configuration_service import AIConfigurationService

router = APIRouter(prefix="/ai-configurations", tags=["AI Configurations"])


def _to_read(entity: AIConfiguration) -> AIConfigurationRead:
    return AIConfigurationRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[AIConfigurationRead],
    dependencies=[Depends(require_permissions(PermissionCode.AI_CONFIGURATIONS_READ))],
)
async def list_ai_configurations(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AIConfigurationRead]:
    service = AIConfigurationService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[AIConfigurationRead],
    dependencies=[Depends(require_permissions(PermissionCode.AI_CONFIGURATIONS_DELETE))],
)
async def list_deleted_ai_configurations(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AIConfigurationRead]:
    service = AIConfigurationService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "",
    response_model=AIConfigurationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.AI_CONFIGURATIONS_CREATE))],
)
async def create_ai_configuration(
    body: AIConfigurationCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AIConfigurationRead:
    service = AIConfigurationService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=AIConfigurationRead,
    dependencies=[Depends(require_permissions(PermissionCode.AI_CONFIGURATIONS_READ))],
)
async def get_ai_configuration(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> AIConfigurationRead:
    service = AIConfigurationService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=AIConfigurationRead,
    dependencies=[Depends(require_permissions(PermissionCode.AI_CONFIGURATIONS_UPDATE))],
)
async def update_ai_configuration(
    entity_id: uuid.UUID,
    body: AIConfigurationUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AIConfigurationRead:
    service = AIConfigurationService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.AI_CONFIGURATIONS_DELETE))],
)
async def delete_ai_configuration(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = AIConfigurationService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=AIConfigurationRead,
    dependencies=[Depends(require_permissions(PermissionCode.AI_CONFIGURATIONS_DELETE))],
)
async def restore_ai_configuration(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AIConfigurationRead:
    service = AIConfigurationService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
