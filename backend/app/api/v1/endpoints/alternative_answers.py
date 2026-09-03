"""AlternativeAnswer management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.alternative_answer import AlternativeAnswer
from app.schemas.alternative_answer import (
    AlternativeAnswerCreate,
    AlternativeAnswerRead,
    AlternativeAnswerUpdate,
)
from app.schemas.pagination import Page, PageParams
from app.services.alternative_answer_service import AlternativeAnswerService

router = APIRouter(prefix="/alternative-answers", tags=["Alternative Answers"])


def _to_read(entity: AlternativeAnswer) -> AlternativeAnswerRead:
    return AlternativeAnswerRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[AlternativeAnswerRead],
    dependencies=[Depends(require_permissions(PermissionCode.ALTERNATIVE_ANSWERS_READ))],
)
async def list_alternative_answers(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AlternativeAnswerRead]:
    service = AlternativeAnswerService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[AlternativeAnswerRead],
    dependencies=[Depends(require_permissions(PermissionCode.ALTERNATIVE_ANSWERS_DELETE))],
)
async def list_deleted_alternative_answers(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AlternativeAnswerRead]:
    service = AlternativeAnswerService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.ALTERNATIVE_ANSWERS_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_alternative_answers() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.ALTERNATIVE_ANSWERS_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_alternative_answers() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.ALTERNATIVE_ANSWERS_CREATE))],
    summary=(
        "Bulk-create alternative answers, collecting per-item errors instead of aborting the batch"
    ),
)
async def bulk_create_alternative_answers(
    body: list[AlternativeAnswerCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, object]:
    service = AlternativeAnswerService(db)
    created = 0
    errors: list[dict[str, object]] = []
    for index, item in enumerate(body):
        try:
            await service.create(institution_id, item, created_by=current_user.id)
            created += 1
        except (ConflictError, NotFoundError, ValidationAppError) as exc:
            errors.append(
                {"index": index, "answer_key_id": str(item.answer_key_id), "error": exc.message}
            )
    await db.commit()
    return {"created": created, "errors": errors}


@router.post(
    "",
    response_model=AlternativeAnswerRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.ALTERNATIVE_ANSWERS_CREATE))],
)
async def create_alternative_answer(
    body: AlternativeAnswerCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AlternativeAnswerRead:
    service = AlternativeAnswerService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=AlternativeAnswerRead,
    dependencies=[Depends(require_permissions(PermissionCode.ALTERNATIVE_ANSWERS_READ))],
)
async def get_alternative_answer(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> AlternativeAnswerRead:
    service = AlternativeAnswerService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=AlternativeAnswerRead,
    dependencies=[Depends(require_permissions(PermissionCode.ALTERNATIVE_ANSWERS_UPDATE))],
)
async def update_alternative_answer(
    entity_id: uuid.UUID,
    body: AlternativeAnswerUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AlternativeAnswerRead:
    service = AlternativeAnswerService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.ALTERNATIVE_ANSWERS_DELETE))],
)
async def delete_alternative_answer(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = AlternativeAnswerService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=AlternativeAnswerRead,
    dependencies=[Depends(require_permissions(PermissionCode.ALTERNATIVE_ANSWERS_DELETE))],
)
async def restore_alternative_answer(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AlternativeAnswerRead:
    service = AlternativeAnswerService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
