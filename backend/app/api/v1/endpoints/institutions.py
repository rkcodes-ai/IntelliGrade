"""
Institution management endpoints.

Institution is the tenant root — unlike every other Module 03 endpoint, it
does NOT depend on `CurrentInstitutionDep` (there is no parent tenant to
resolve). Access is gated purely by permission codes; only `super_admin`
is granted `INSTITUTIONS_CREATE`/`INSTITUTIONS_DELETE` by default (see
`DEFAULT_ROLE_PERMISSIONS` in `app/core/constants.py`).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.models.institution import Institution
from app.models.user_institution import UserInstitution
from app.schemas.institution import (
    InstitutionCreate,
    InstitutionRead,
    InstitutionUpdate,
    UserInstitutionAssign,
    UserInstitutionRead,
)
from app.schemas.pagination import Page, PageParams
from app.services.institution_service import InstitutionService

router = APIRouter(prefix="/institutions", tags=["Institutions"])


def _to_read(institution: Institution) -> InstitutionRead:
    return InstitutionRead.model_validate(institution)


def _membership_to_read(membership: UserInstitution) -> UserInstitutionRead:
    return UserInstitutionRead.model_validate(membership)


@router.get(
    "",
    response_model=Page[InstitutionRead],
    dependencies=[Depends(require_permissions(PermissionCode.INSTITUTIONS_READ))],
    summary="List institutions",
)
async def list_institutions(
    db: DbSession, params: Annotated[PageParams, Depends()]
) -> Page[InstitutionRead]:
    service = InstitutionService(db)
    items, total = await service.list_paginated(params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[InstitutionRead],
    dependencies=[Depends(require_permissions(PermissionCode.INSTITUTIONS_DELETE))],
    summary="List soft-deleted institutions (for restore)",
)
async def list_deleted_institutions(
    db: DbSession, params: Annotated[PageParams, Depends()]
) -> Page[InstitutionRead]:
    service = InstitutionService(db)
    items, total = await service.list_deleted(params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/mine",
    response_model=list[InstitutionRead],
    summary="List institutions the current user may select as their active tenant",
)
async def list_my_institutions(
    db: DbSession, current_user: CurrentUserDep
) -> list[InstitutionRead]:
    service = InstitutionService(db)
    institutions = await service.list_mine(current_user)
    return [_to_read(i) for i in institutions]


@router.post(
    "",
    response_model=InstitutionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.INSTITUTIONS_CREATE))],
    summary="Create an institution",
)
async def create_institution(
    body: InstitutionCreate, db: DbSession, current_user: CurrentUserDep
) -> InstitutionRead:
    service = InstitutionService(db)
    institution = await service.create(body, created_by=current_user.id)
    await db.commit()
    return _to_read(institution)


@router.get(
    "/{institution_id}",
    response_model=InstitutionRead,
    dependencies=[Depends(require_permissions(PermissionCode.INSTITUTIONS_READ))],
    summary="Get an institution by ID",
)
async def get_institution(institution_id: uuid.UUID, db: DbSession) -> InstitutionRead:
    service = InstitutionService(db)
    institution = await service.get_by_id(institution_id)
    return _to_read(institution)


@router.patch(
    "/{institution_id}",
    response_model=InstitutionRead,
    dependencies=[Depends(require_permissions(PermissionCode.INSTITUTIONS_UPDATE))],
    summary="Update an institution",
)
async def update_institution(
    institution_id: uuid.UUID,
    body: InstitutionUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> InstitutionRead:
    service = InstitutionService(db)
    institution = await service.update(institution_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(institution)


@router.delete(
    "/{institution_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.INSTITUTIONS_DELETE))],
    summary="Soft-delete an institution",
)
async def delete_institution(
    institution_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep
) -> None:
    service = InstitutionService(db)
    await service.soft_delete(institution_id, actor_id=current_user.id)
    await db.commit()


@router.post(
    "/{institution_id}/restore",
    response_model=InstitutionRead,
    dependencies=[Depends(require_permissions(PermissionCode.INSTITUTIONS_DELETE))],
    summary="Restore a soft-deleted institution",
)
async def restore_institution(
    institution_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep
) -> InstitutionRead:
    service = InstitutionService(db)
    institution = await service.restore(institution_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(institution)


@router.get(
    "/{institution_id}/members",
    response_model=list[UserInstitutionRead],
    dependencies=[Depends(require_permissions(PermissionCode.INSTITUTIONS_READ))],
    summary="List an institution's user memberships",
)
async def list_institution_members(
    institution_id: uuid.UUID, db: DbSession
) -> list[UserInstitutionRead]:
    service = InstitutionService(db)
    members = await service.list_members(institution_id)
    return [_membership_to_read(m) for m in members]


@router.post(
    "/{institution_id}/members",
    response_model=UserInstitutionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.INSTITUTIONS_UPDATE))],
    summary="Add a user to an institution",
)
async def assign_institution_member(
    institution_id: uuid.UUID,
    body: UserInstitutionAssign,
    db: DbSession,
    current_user: CurrentUserDep,
) -> UserInstitutionRead:
    service = InstitutionService(db)
    membership = await service.assign_user(
        institution_id, body.user_id, is_primary=body.is_primary, assigned_by=current_user.id
    )
    await db.commit()
    return _membership_to_read(membership)


@router.delete(
    "/{institution_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.INSTITUTIONS_UPDATE))],
    summary="Remove a user from an institution",
)
async def revoke_institution_member(
    institution_id: uuid.UUID,
    user_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUserDep,
) -> None:
    service = InstitutionService(db)
    await service.revoke_user(institution_id, user_id, revoked_by=current_user.id)
    await db.commit()
