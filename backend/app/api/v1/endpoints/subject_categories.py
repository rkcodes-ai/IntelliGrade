"""SubjectCategory management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.subject_category import SubjectCategory
from app.schemas.pagination import Page, PageParams
from app.schemas.subject_category import (
    SubjectCategoryCreate,
    SubjectCategoryRead,
    SubjectCategoryUpdate,
)
from app.services.subject_category_service import SubjectCategoryService

router = APIRouter(prefix="/subject-categories", tags=["Subject Categories"])


def _to_read(entity: SubjectCategory) -> SubjectCategoryRead:
    return SubjectCategoryRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[SubjectCategoryRead],
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_CATEGORIES_READ))],
)
async def list_subject_categories(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[SubjectCategoryRead]:
    service = SubjectCategoryService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[SubjectCategoryRead],
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_CATEGORIES_DELETE))],
)
async def list_deleted_subject_categories(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[SubjectCategoryRead]:
    service = SubjectCategoryService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_CATEGORIES_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_subject_categories() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_CATEGORIES_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_subject_categories() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_CATEGORIES_CREATE))],
    summary="Bulk-create subject categories, collecting per-item errors instead of aborting",
)
async def bulk_create_subject_categories(
    body: list[SubjectCategoryCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, object]:
    service = SubjectCategoryService(db)
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
    response_model=SubjectCategoryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_CATEGORIES_CREATE))],
)
async def create_subject_category(
    body: SubjectCategoryCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> SubjectCategoryRead:
    service = SubjectCategoryService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=SubjectCategoryRead,
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_CATEGORIES_READ))],
)
async def get_subject_category(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> SubjectCategoryRead:
    service = SubjectCategoryService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=SubjectCategoryRead,
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_CATEGORIES_UPDATE))],
)
async def update_subject_category(
    entity_id: uuid.UUID,
    body: SubjectCategoryUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> SubjectCategoryRead:
    service = SubjectCategoryService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_CATEGORIES_DELETE))],
)
async def delete_subject_category(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = SubjectCategoryService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=SubjectCategoryRead,
    dependencies=[Depends(require_permissions(PermissionCode.SUBJECT_CATEGORIES_DELETE))],
)
async def restore_subject_category(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> SubjectCategoryRead:
    service = SubjectCategoryService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    # `TenantScopedService.restore` (shared infra) leaves `updated_at`
    # (onupdate=func.now()) expired after its flush on SQLite/aiosqlite (no
    # eager RETURNING fetch on UPDATE) — refresh here, before serializing,
    # so the synchronous Pydantic read below doesn't trigger a lazy load
    # outside of greenlet context (`MissingGreenlet`).
    await db.refresh(entity)
    await db.commit()
    return _to_read(entity)
