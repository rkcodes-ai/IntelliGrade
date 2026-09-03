"""Teacher assignment management endpoints."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import AppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.teacher_assignment import TeacherAssignment
from app.schemas.pagination import Page, PageParams
from app.schemas.teacher_assignment import (
    TeacherAssignmentCreate,
    TeacherAssignmentRead,
    TeacherAssignmentUpdate,
)
from app.services.teacher_assignment_service import TeacherAssignmentService

router = APIRouter(prefix="/teacher-assignments", tags=["Teacher Assignments"])


def _to_read(entity: TeacherAssignment) -> TeacherAssignmentRead:
    return TeacherAssignmentRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[TeacherAssignmentRead],
    dependencies=[Depends(require_permissions(PermissionCode.TEACHER_ASSIGNMENTS_READ))],
)
async def list_teacher_assignments(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[TeacherAssignmentRead]:
    service = TeacherAssignmentService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[TeacherAssignmentRead],
    dependencies=[Depends(require_permissions(PermissionCode.TEACHER_ASSIGNMENTS_DELETE))],
)
async def list_deleted_teacher_assignments(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[TeacherAssignmentRead]:
    service = TeacherAssignmentService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.TEACHER_ASSIGNMENTS_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_teacher_assignments() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.TEACHER_ASSIGNMENTS_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_teacher_assignments() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.TEACHER_ASSIGNMENTS_CREATE))],
    summary="Bulk-create teacher assignments",
)
async def bulk_create_teacher_assignments(
    body: list[TeacherAssignmentCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, Any]:
    service = TeacherAssignmentService(db)
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
    response_model=TeacherAssignmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.TEACHER_ASSIGNMENTS_CREATE))],
)
async def create_teacher_assignment(
    body: TeacherAssignmentCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> TeacherAssignmentRead:
    service = TeacherAssignmentService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=TeacherAssignmentRead,
    dependencies=[Depends(require_permissions(PermissionCode.TEACHER_ASSIGNMENTS_READ))],
)
async def get_teacher_assignment(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> TeacherAssignmentRead:
    service = TeacherAssignmentService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=TeacherAssignmentRead,
    dependencies=[Depends(require_permissions(PermissionCode.TEACHER_ASSIGNMENTS_UPDATE))],
)
async def update_teacher_assignment(
    entity_id: uuid.UUID,
    body: TeacherAssignmentUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> TeacherAssignmentRead:
    service = TeacherAssignmentService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.TEACHER_ASSIGNMENTS_DELETE))],
)
async def delete_teacher_assignment(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = TeacherAssignmentService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=TeacherAssignmentRead,
    dependencies=[Depends(require_permissions(PermissionCode.TEACHER_ASSIGNMENTS_DELETE))],
)
async def restore_teacher_assignment(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> TeacherAssignmentRead:
    service = TeacherAssignmentService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
