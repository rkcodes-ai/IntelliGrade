"""QuestionCategory management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.question_category import QuestionCategory
from app.schemas.pagination import Page, PageParams
from app.schemas.question_category import (
    QuestionCategoryCreate,
    QuestionCategoryRead,
    QuestionCategoryUpdate,
)
from app.services.question_category_service import QuestionCategoryService

router = APIRouter(prefix="/question-categories", tags=["Question Categories"])


def _to_read(entity: QuestionCategory) -> QuestionCategoryRead:
    return QuestionCategoryRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[QuestionCategoryRead],
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_CATEGORIES_READ))],
)
async def list_question_categories(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[QuestionCategoryRead]:
    service = QuestionCategoryService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[QuestionCategoryRead],
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_CATEGORIES_DELETE))],
)
async def list_deleted_question_categories(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[QuestionCategoryRead]:
    service = QuestionCategoryService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_CATEGORIES_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_question_categories() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_CATEGORIES_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_question_categories() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_CATEGORIES_CREATE))],
    summary="Bulk-create question categories, collecting per-item errors instead of aborting",
)
async def bulk_create_question_categories(
    body: list[QuestionCategoryCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, object]:
    service = QuestionCategoryService(db)
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
    response_model=QuestionCategoryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_CATEGORIES_CREATE))],
)
async def create_question_category(
    body: QuestionCategoryCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionCategoryRead:
    service = QuestionCategoryService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=QuestionCategoryRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_CATEGORIES_READ))],
)
async def get_question_category(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> QuestionCategoryRead:
    service = QuestionCategoryService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=QuestionCategoryRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_CATEGORIES_UPDATE))],
)
async def update_question_category(
    entity_id: uuid.UUID,
    body: QuestionCategoryUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionCategoryRead:
    service = QuestionCategoryService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_CATEGORIES_DELETE))],
)
async def delete_question_category(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = QuestionCategoryService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=QuestionCategoryRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_CATEGORIES_DELETE))],
)
async def restore_question_category(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionCategoryRead:
    service = QuestionCategoryService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
