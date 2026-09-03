"""
QuestionVersion browsing endpoints — append-only snapshot history for `Question`.

Rows are created exclusively via `POST /api/v1/questions/{question_id}/versions`
(`app/api/v1/endpoints/questions.py`, `QuestionVersionService.create_snapshot`),
never through this router — versions are immutable once created, so there is
deliberately no `POST ""` or `PATCH "/{entity_id}"` here. Soft-delete/restore
are still exposed for consistency with every other entity in this codebase,
even though they are rarely used against an append-only log.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.question_version import QuestionVersion
from app.schemas.pagination import Page, PageParams
from app.schemas.question_version import QuestionVersionRead
from app.services.question_version_service import QuestionVersionService

router = APIRouter(prefix="/question-versions", tags=["Question Versions"])


def _to_read(entity: QuestionVersion) -> QuestionVersionRead:
    return QuestionVersionRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[QuestionVersionRead],
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_VERSIONS_READ))],
)
async def list_question_versions(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[QuestionVersionRead]:
    service = QuestionVersionService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[QuestionVersionRead],
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_VERSIONS_DELETE))],
)
async def list_deleted_question_versions(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[QuestionVersionRead]:
    service = QuestionVersionService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/{entity_id}",
    response_model=QuestionVersionRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_VERSIONS_READ))],
)
async def get_question_version(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> QuestionVersionRead:
    service = QuestionVersionService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_VERSIONS_DELETE))],
)
async def delete_question_version(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = QuestionVersionService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=QuestionVersionRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_VERSIONS_DELETE))],
)
async def restore_question_version(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionVersionRead:
    service = QuestionVersionService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
