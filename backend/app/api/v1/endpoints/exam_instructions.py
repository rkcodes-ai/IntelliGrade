"""Exam instructions management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.exam_instructions import ExamInstructions
from app.schemas.exam_instructions import (
    ExamInstructionsCreate,
    ExamInstructionsRead,
    ExamInstructionsUpdate,
)
from app.schemas.pagination import Page, PageParams
from app.services.exam_instructions_service import ExamInstructionsService

router = APIRouter(prefix="/exam-instructions", tags=["Exam Instructions"])


def _to_read(entity: ExamInstructions) -> ExamInstructionsRead:
    return ExamInstructionsRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[ExamInstructionsRead],
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_INSTRUCTIONS_READ))],
)
async def list_exam_instructions(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[ExamInstructionsRead]:
    service = ExamInstructionsService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[ExamInstructionsRead],
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_INSTRUCTIONS_DELETE))],
)
async def list_deleted_exam_instructions(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[ExamInstructionsRead]:
    service = ExamInstructionsService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_INSTRUCTIONS_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_exam_instructions() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_INSTRUCTIONS_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_exam_instructions() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_INSTRUCTIONS_CREATE))],
    summary="Bulk-create exam instructions, collecting per-item errors instead of aborting",
)
async def bulk_create_exam_instructions(
    body: list[ExamInstructionsCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, object]:
    service = ExamInstructionsService(db)
    created = 0
    errors: list[dict[str, object]] = []
    for index, item in enumerate(body):
        try:
            await service.create(institution_id, item, created_by=current_user.id)
            created += 1
        except (ConflictError, NotFoundError, ValidationAppError) as exc:
            errors.append({"index": index, "exam_id": str(item.exam_id), "error": exc.message})
    await db.commit()
    return {"created": created, "errors": errors}


@router.post(
    "",
    response_model=ExamInstructionsRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_INSTRUCTIONS_CREATE))],
)
async def create_exam_instructions(
    body: ExamInstructionsCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ExamInstructionsRead:
    service = ExamInstructionsService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=ExamInstructionsRead,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_INSTRUCTIONS_READ))],
)
async def get_exam_instructions(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> ExamInstructionsRead:
    service = ExamInstructionsService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=ExamInstructionsRead,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_INSTRUCTIONS_UPDATE))],
)
async def update_exam_instructions(
    entity_id: uuid.UUID,
    body: ExamInstructionsUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ExamInstructionsRead:
    service = ExamInstructionsService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_INSTRUCTIONS_DELETE))],
)
async def delete_exam_instructions(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = ExamInstructionsService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=ExamInstructionsRead,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_INSTRUCTIONS_DELETE))],
)
async def restore_exam_instructions(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ExamInstructionsRead:
    service = ExamInstructionsService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
