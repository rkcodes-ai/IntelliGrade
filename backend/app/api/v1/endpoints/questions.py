"""Question management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.question import Question
from app.models.question_tag_map import QuestionTagMap
from app.schemas.pagination import Page, PageParams
from app.schemas.question import (
    QuestionCreate,
    QuestionRead,
    QuestionRejectRequest,
    QuestionTagAddRequest,
    QuestionTagMapRead,
    QuestionUpdate,
)
from app.schemas.question_version import QuestionVersionRead, QuestionVersionSnapshotRequest
from app.services.question_service import QuestionService
from app.services.question_version_service import QuestionVersionService

router = APIRouter(prefix="/questions", tags=["Questions"])


def _to_read(entity: Question) -> QuestionRead:
    return QuestionRead.model_validate(entity)


def _tag_to_read(entity: QuestionTagMap) -> QuestionTagMapRead:
    return QuestionTagMapRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[QuestionRead],
    dependencies=[Depends(require_permissions(PermissionCode.QUESTIONS_READ))],
)
async def list_questions(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[QuestionRead]:
    service = QuestionService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[QuestionRead],
    dependencies=[Depends(require_permissions(PermissionCode.QUESTIONS_DELETE))],
)
async def list_deleted_questions(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[QuestionRead]:
    service = QuestionService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTIONS_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_questions() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 04 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.QUESTIONS_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_questions() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 04 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTIONS_CREATE))],
    summary="Bulk-create questions, collecting per-item errors instead of aborting the batch",
)
async def bulk_create_questions(
    body: list[QuestionCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, object]:
    service = QuestionService(db)
    created = 0
    errors: list[dict[str, object]] = []
    for index, item in enumerate(body):
        try:
            await service.create(institution_id, item, created_by=current_user.id)
            created += 1
        except (ConflictError, NotFoundError, ValidationAppError) as exc:
            errors.append({"index": index, "error": exc.message})
    await db.commit()
    return {"created": created, "errors": errors}


@router.post(
    "",
    response_model=QuestionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTIONS_CREATE))],
)
async def create_question(
    body: QuestionCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionRead:
    service = QuestionService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=QuestionRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTIONS_READ))],
)
async def get_question(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> QuestionRead:
    service = QuestionService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=QuestionRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTIONS_UPDATE))],
)
async def update_question(
    entity_id: uuid.UUID,
    body: QuestionUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionRead:
    service = QuestionService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTIONS_DELETE))],
)
async def delete_question(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = QuestionService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=QuestionRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTIONS_DELETE))],
)
async def restore_question(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionRead:
    service = QuestionService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/submit-for-review",
    response_model=QuestionRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTIONS_UPDATE))],
)
async def submit_question_for_review(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionRead:
    service = QuestionService(db)
    entity = await service.submit_for_review(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/approve",
    response_model=QuestionRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTIONS_APPROVE))],
)
async def approve_question(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionRead:
    service = QuestionService(db)
    entity = await service.approve(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/reject",
    response_model=QuestionRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTIONS_REJECT))],
)
async def reject_question(
    entity_id: uuid.UUID,
    body: QuestionRejectRequest,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionRead:
    service = QuestionService(db)
    entity = await service.reject(
        institution_id, entity_id, reason=body.reason, actor_id=current_user.id
    )
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/tags",
    response_model=QuestionTagMapRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTIONS_UPDATE))],
)
async def add_question_tag(
    entity_id: uuid.UUID,
    body: QuestionTagAddRequest,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionTagMapRead:
    service = QuestionService(db)
    tag_map = await service.add_tag(institution_id, entity_id, body.tag_id)
    await db.commit()
    return _tag_to_read(tag_map)


@router.delete(
    "/{entity_id}/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTIONS_UPDATE))],
)
async def remove_question_tag(
    entity_id: uuid.UUID,
    tag_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = QuestionService(db)
    await service.remove_tag(institution_id, entity_id, tag_id)
    await db.commit()


@router.post(
    "/{question_id}/versions",
    response_model=QuestionVersionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_VERSIONS_CREATE))],
    summary="Snapshot this question's current state into a new, immutable QuestionVersion row",
)
async def create_question_version_snapshot(
    question_id: uuid.UUID,
    body: QuestionVersionSnapshotRequest,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionVersionRead:
    service = QuestionVersionService(db)
    entity = await service.create_snapshot(
        institution_id, question_id, body.change_reason, created_by=current_user.id
    )
    await db.commit()
    return QuestionVersionRead.model_validate(entity)
