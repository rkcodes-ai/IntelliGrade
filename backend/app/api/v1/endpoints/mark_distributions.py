"""MarkDistribution management endpoints."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import AppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.mark_distribution import MarkDistribution
from app.schemas.mark_distribution import (
    MarkDistributionCreate,
    MarkDistributionRead,
    MarkDistributionUpdate,
)
from app.schemas.pagination import Page, PageParams
from app.services.mark_distribution_service import MarkDistributionService

router = APIRouter(prefix="/mark-distributions", tags=["Mark Distributions"])


def _to_read(entity: MarkDistribution) -> MarkDistributionRead:
    return MarkDistributionRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[MarkDistributionRead],
    dependencies=[Depends(require_permissions(PermissionCode.MARK_DISTRIBUTIONS_READ))],
)
async def list_mark_distributions(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[MarkDistributionRead]:
    service = MarkDistributionService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[MarkDistributionRead],
    dependencies=[Depends(require_permissions(PermissionCode.MARK_DISTRIBUTIONS_DELETE))],
)
async def list_deleted_mark_distributions(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[MarkDistributionRead]:
    service = MarkDistributionService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.MARK_DISTRIBUTIONS_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_mark_distributions() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.MARK_DISTRIBUTIONS_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_mark_distributions() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.MARK_DISTRIBUTIONS_CREATE))],
    summary="Bulk-create mark distributions, collecting per-item errors instead of aborting",
)
async def bulk_create_mark_distributions(
    body: list[MarkDistributionCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, Any]:
    service = MarkDistributionService(db)
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
    response_model=MarkDistributionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.MARK_DISTRIBUTIONS_CREATE))],
)
async def create_mark_distribution(
    body: MarkDistributionCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> MarkDistributionRead:
    service = MarkDistributionService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=MarkDistributionRead,
    dependencies=[Depends(require_permissions(PermissionCode.MARK_DISTRIBUTIONS_READ))],
)
async def get_mark_distribution(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> MarkDistributionRead:
    service = MarkDistributionService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=MarkDistributionRead,
    dependencies=[Depends(require_permissions(PermissionCode.MARK_DISTRIBUTIONS_UPDATE))],
)
async def update_mark_distribution(
    entity_id: uuid.UUID,
    body: MarkDistributionUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> MarkDistributionRead:
    service = MarkDistributionService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.MARK_DISTRIBUTIONS_DELETE))],
)
async def delete_mark_distribution(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = MarkDistributionService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=MarkDistributionRead,
    dependencies=[Depends(require_permissions(PermissionCode.MARK_DISTRIBUTIONS_DELETE))],
)
async def restore_mark_distribution(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> MarkDistributionRead:
    service = MarkDistributionService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
