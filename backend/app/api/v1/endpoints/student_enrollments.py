"""Student enrollment management endpoints."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import AppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.student_enrollment import StudentEnrollment
from app.schemas.pagination import Page, PageParams
from app.schemas.student_enrollment import (
    StudentEnrollmentCreate,
    StudentEnrollmentRead,
    StudentEnrollmentStatusChange,
    StudentEnrollmentUpdate,
)
from app.services.student_enrollment_service import StudentEnrollmentService

router = APIRouter(prefix="/student-enrollments", tags=["Student Enrollments"])


def _to_read(entity: StudentEnrollment) -> StudentEnrollmentRead:
    return StudentEnrollmentRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[StudentEnrollmentRead],
    dependencies=[Depends(require_permissions(PermissionCode.STUDENT_ENROLLMENTS_READ))],
)
async def list_student_enrollments(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[StudentEnrollmentRead]:
    service = StudentEnrollmentService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[StudentEnrollmentRead],
    dependencies=[Depends(require_permissions(PermissionCode.STUDENT_ENROLLMENTS_DELETE))],
)
async def list_deleted_student_enrollments(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[StudentEnrollmentRead]:
    service = StudentEnrollmentService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.STUDENT_ENROLLMENTS_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_student_enrollments() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.STUDENT_ENROLLMENTS_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_student_enrollments() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.STUDENT_ENROLLMENTS_CREATE))],
    summary="Bulk-create student enrollments",
)
async def bulk_create_student_enrollments(
    body: list[StudentEnrollmentCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, Any]:
    service = StudentEnrollmentService(db)
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
    response_model=StudentEnrollmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.STUDENT_ENROLLMENTS_CREATE))],
)
async def create_student_enrollment(
    body: StudentEnrollmentCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> StudentEnrollmentRead:
    service = StudentEnrollmentService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=StudentEnrollmentRead,
    dependencies=[Depends(require_permissions(PermissionCode.STUDENT_ENROLLMENTS_READ))],
)
async def get_student_enrollment(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> StudentEnrollmentRead:
    service = StudentEnrollmentService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=StudentEnrollmentRead,
    dependencies=[Depends(require_permissions(PermissionCode.STUDENT_ENROLLMENTS_UPDATE))],
)
async def update_student_enrollment(
    entity_id: uuid.UUID,
    body: StudentEnrollmentUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> StudentEnrollmentRead:
    service = StudentEnrollmentService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.patch(
    "/{entity_id}/status",
    response_model=StudentEnrollmentRead,
    dependencies=[Depends(require_permissions(PermissionCode.STUDENT_ENROLLMENTS_UPDATE))],
    summary="Change a student enrollment's academic status",
)
async def change_student_enrollment_status(
    entity_id: uuid.UUID,
    body: StudentEnrollmentStatusChange,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> StudentEnrollmentRead:
    service = StudentEnrollmentService(db)
    entity = await service.change_status(
        institution_id, entity_id, body.new_status_id, actor_id=current_user.id
    )
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.STUDENT_ENROLLMENTS_DELETE))],
)
async def delete_student_enrollment(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = StudentEnrollmentService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=StudentEnrollmentRead,
    dependencies=[Depends(require_permissions(PermissionCode.STUDENT_ENROLLMENTS_DELETE))],
)
async def restore_student_enrollment(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> StudentEnrollmentRead:
    service = StudentEnrollmentService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
