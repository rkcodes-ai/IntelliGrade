"""ReferenceNote management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.reference_note import ReferenceNote
from app.schemas.pagination import Page, PageParams
from app.schemas.reference_note import ReferenceNoteCreate, ReferenceNoteRead, ReferenceNoteUpdate
from app.services.reference_note_service import ReferenceNoteService

router = APIRouter(prefix="/reference-notes", tags=["Reference Notes"])


def _to_read(entity: ReferenceNote) -> ReferenceNoteRead:
    return ReferenceNoteRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[ReferenceNoteRead],
    dependencies=[Depends(require_permissions(PermissionCode.REFERENCE_NOTES_READ))],
)
async def list_reference_notes(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[ReferenceNoteRead]:
    service = ReferenceNoteService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[ReferenceNoteRead],
    dependencies=[Depends(require_permissions(PermissionCode.REFERENCE_NOTES_DELETE))],
)
async def list_deleted_reference_notes(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[ReferenceNoteRead]:
    service = ReferenceNoteService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.REFERENCE_NOTES_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_reference_notes() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.REFERENCE_NOTES_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_reference_notes() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.REFERENCE_NOTES_CREATE))],
    summary="Bulk-create reference notes, collecting per-item errors instead of aborting the batch",
)
async def bulk_create_reference_notes(
    body: list[ReferenceNoteCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, object]:
    service = ReferenceNoteService(db)
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
    response_model=ReferenceNoteRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.REFERENCE_NOTES_CREATE))],
)
async def create_reference_note(
    body: ReferenceNoteCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ReferenceNoteRead:
    service = ReferenceNoteService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=ReferenceNoteRead,
    dependencies=[Depends(require_permissions(PermissionCode.REFERENCE_NOTES_READ))],
)
async def get_reference_note(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> ReferenceNoteRead:
    service = ReferenceNoteService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=ReferenceNoteRead,
    dependencies=[Depends(require_permissions(PermissionCode.REFERENCE_NOTES_UPDATE))],
)
async def update_reference_note(
    entity_id: uuid.UUID,
    body: ReferenceNoteUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ReferenceNoteRead:
    service = ReferenceNoteService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.REFERENCE_NOTES_DELETE))],
)
async def delete_reference_note(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = ReferenceNoteService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=ReferenceNoteRead,
    dependencies=[Depends(require_permissions(PermissionCode.REFERENCE_NOTES_DELETE))],
)
async def restore_reference_note(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ReferenceNoteRead:
    service = ReferenceNoteService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
