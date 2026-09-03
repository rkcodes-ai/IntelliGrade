"""RandomizationStrategy management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import AppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.randomization_strategy import RandomizationStrategy
from app.schemas.pagination import Page, PageParams
from app.schemas.randomization_strategy import (
    RandomizationStrategyCreate,
    RandomizationStrategyRead,
    RandomizationStrategyUpdate,
)
from app.services.randomization_strategy_service import RandomizationStrategyService

router = APIRouter(prefix="/randomization-strategies", tags=["Randomization Strategies"])


def _to_read(entity: RandomizationStrategy) -> RandomizationStrategyRead:
    return RandomizationStrategyRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[RandomizationStrategyRead],
    dependencies=[Depends(require_permissions(PermissionCode.RANDOMIZATION_STRATEGIES_READ))],
)
async def list_randomization_strategies(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[RandomizationStrategyRead]:
    service = RandomizationStrategyService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[RandomizationStrategyRead],
    dependencies=[Depends(require_permissions(PermissionCode.RANDOMIZATION_STRATEGIES_DELETE))],
)
async def list_deleted_randomization_strategies(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[RandomizationStrategyRead]:
    service = RandomizationStrategyService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.RANDOMIZATION_STRATEGIES_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_randomization_strategies() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 04 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.RANDOMIZATION_STRATEGIES_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_randomization_strategies() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 04 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.RANDOMIZATION_STRATEGIES_CREATE))],
    summary="Bulk-create randomization strategies, collecting per-item errors instead of aborting",
)
async def bulk_create_randomization_strategies(
    body: list[RandomizationStrategyCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, object]:
    service = RandomizationStrategyService(db)
    created = 0
    errors: list[dict[str, object]] = []
    for index, item in enumerate(body):
        try:
            await service.create(institution_id, item, created_by=current_user.id)
            created += 1
        except AppError as exc:
            errors.append({"index": index, "error": exc.message})
    await db.commit()
    return {"created": created, "errors": errors}


@router.post(
    "",
    response_model=RandomizationStrategyRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.RANDOMIZATION_STRATEGIES_CREATE))],
)
async def create_randomization_strategy(
    body: RandomizationStrategyCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> RandomizationStrategyRead:
    service = RandomizationStrategyService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=RandomizationStrategyRead,
    dependencies=[Depends(require_permissions(PermissionCode.RANDOMIZATION_STRATEGIES_READ))],
)
async def get_randomization_strategy(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> RandomizationStrategyRead:
    service = RandomizationStrategyService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=RandomizationStrategyRead,
    dependencies=[Depends(require_permissions(PermissionCode.RANDOMIZATION_STRATEGIES_UPDATE))],
)
async def update_randomization_strategy(
    entity_id: uuid.UUID,
    body: RandomizationStrategyUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> RandomizationStrategyRead:
    service = RandomizationStrategyService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.RANDOMIZATION_STRATEGIES_DELETE))],
)
async def delete_randomization_strategy(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = RandomizationStrategyService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=RandomizationStrategyRead,
    dependencies=[Depends(require_permissions(PermissionCode.RANDOMIZATION_STRATEGIES_DELETE))],
)
async def restore_randomization_strategy(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> RandomizationStrategyRead:
    service = RandomizationStrategyService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
