"""AttendancePolicy management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.attendance_policy import AttendancePolicy
from app.schemas.attendance_policy import (
    AttendancePolicyCreate,
    AttendancePolicyRead,
    AttendancePolicyUpdate,
)
from app.schemas.pagination import Page, PageParams
from app.services.attendance_policy_service import AttendancePolicyService

router = APIRouter(prefix="/attendance-policies", tags=["Attendance Policies"])


def _to_read(entity: AttendancePolicy) -> AttendancePolicyRead:
    return AttendancePolicyRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[AttendancePolicyRead],
    dependencies=[Depends(require_permissions(PermissionCode.ATTENDANCE_POLICIES_READ))],
)
async def list_attendance_policies(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AttendancePolicyRead]:
    service = AttendancePolicyService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[AttendancePolicyRead],
    dependencies=[Depends(require_permissions(PermissionCode.ATTENDANCE_POLICIES_DELETE))],
)
async def list_deleted_attendance_policies(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AttendancePolicyRead]:
    service = AttendancePolicyService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.ATTENDANCE_POLICIES_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_attendance_policies() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 03 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.ATTENDANCE_POLICIES_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_attendance_policies() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 03 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.ATTENDANCE_POLICIES_CREATE))],
    summary="Bulk-create attendance policies, collecting per-item errors instead of aborting",
)
async def bulk_create_attendance_policies(
    body: list[AttendancePolicyCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, object]:
    service = AttendancePolicyService(db)
    created = 0
    errors: list[dict[str, object]] = []
    for index, item in enumerate(body):
        try:
            await service.create(institution_id, item, created_by=current_user.id)
            created += 1
        except (ConflictError, NotFoundError, ValidationAppError) as exc:
            errors.append({"index": index, "name": item.name, "error": exc.message})
    await db.commit()
    return {"created": created, "errors": errors}


@router.post(
    "",
    response_model=AttendancePolicyRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.ATTENDANCE_POLICIES_CREATE))],
)
async def create_attendance_policy(
    body: AttendancePolicyCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AttendancePolicyRead:
    service = AttendancePolicyService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=AttendancePolicyRead,
    dependencies=[Depends(require_permissions(PermissionCode.ATTENDANCE_POLICIES_READ))],
)
async def get_attendance_policy(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> AttendancePolicyRead:
    service = AttendancePolicyService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=AttendancePolicyRead,
    dependencies=[Depends(require_permissions(PermissionCode.ATTENDANCE_POLICIES_UPDATE))],
)
async def update_attendance_policy(
    entity_id: uuid.UUID,
    body: AttendancePolicyUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AttendancePolicyRead:
    service = AttendancePolicyService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.ATTENDANCE_POLICIES_DELETE))],
)
async def delete_attendance_policy(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = AttendancePolicyService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=AttendancePolicyRead,
    dependencies=[Depends(require_permissions(PermissionCode.ATTENDANCE_POLICIES_DELETE))],
)
async def restore_attendance_policy(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AttendancePolicyRead:
    service = AttendancePolicyService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    # See `subject_categories.restore_subject_category` for why this refresh
    # is needed (avoids a post-flush `MissingGreenlet` on `updated_at`).
    await db.refresh(entity)
    await db.commit()
    return _to_read(entity)
