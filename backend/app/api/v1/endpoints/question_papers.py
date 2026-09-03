"""QuestionPaper management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.question_paper import QuestionPaper
from app.schemas.pagination import Page, PageParams
from app.schemas.question_paper import (
    QuestionPaperCreate,
    QuestionPaperRead,
    QuestionPaperRejectRequest,
    QuestionPaperUpdate,
)
from app.schemas.question_paper_version import (
    QuestionPaperVersionRead,
    QuestionPaperVersionSnapshotRequest,
)
from app.services.question_paper_service import QuestionPaperService
from app.services.question_paper_version_service import QuestionPaperVersionService

router = APIRouter(prefix="/question-papers", tags=["Question Papers"])


def _to_read(entity: QuestionPaper) -> QuestionPaperRead:
    return QuestionPaperRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[QuestionPaperRead],
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPERS_READ))],
)
async def list_question_papers(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[QuestionPaperRead]:
    service = QuestionPaperService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[QuestionPaperRead],
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPERS_DELETE))],
)
async def list_deleted_question_papers(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[QuestionPaperRead]:
    service = QuestionPaperService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPERS_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_question_papers() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 04 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPERS_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_question_papers() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 04 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPERS_CREATE))],
    summary="Bulk-create question papers, collecting per-item errors instead of aborting the batch",
)
async def bulk_create_question_papers(
    body: list[QuestionPaperCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, object]:
    service = QuestionPaperService(db)
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
    response_model=QuestionPaperRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPERS_CREATE))],
)
async def create_question_paper(
    body: QuestionPaperCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionPaperRead:
    service = QuestionPaperService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=QuestionPaperRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPERS_READ))],
)
async def get_question_paper(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> QuestionPaperRead:
    service = QuestionPaperService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=QuestionPaperRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPERS_UPDATE))],
)
async def update_question_paper(
    entity_id: uuid.UUID,
    body: QuestionPaperUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionPaperRead:
    service = QuestionPaperService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPERS_DELETE))],
)
async def delete_question_paper(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = QuestionPaperService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=QuestionPaperRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPERS_DELETE))],
)
async def restore_question_paper(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionPaperRead:
    service = QuestionPaperService(db)
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
    response_model=QuestionPaperRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPERS_UPDATE))],
)
async def submit_question_paper_for_review(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionPaperRead:
    service = QuestionPaperService(db)
    entity = await service.submit_for_review(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/approve",
    response_model=QuestionPaperRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPERS_APPROVE))],
)
async def approve_question_paper(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionPaperRead:
    service = QuestionPaperService(db)
    entity = await service.approve(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/reject",
    response_model=QuestionPaperRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPERS_REJECT))],
)
async def reject_question_paper(
    entity_id: uuid.UUID,
    body: QuestionPaperRejectRequest,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionPaperRead:
    service = QuestionPaperService(db)
    entity = await service.reject(
        institution_id, entity_id, reason=body.reason, actor_id=current_user.id
    )
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/versions",
    response_model=QuestionPaperVersionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPER_VERSIONS_CREATE))],
)
async def create_question_paper_version(
    entity_id: uuid.UUID,
    body: QuestionPaperVersionSnapshotRequest,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionPaperVersionRead:
    paper_service = QuestionPaperService(db)
    paper = await paper_service.get_by_id(institution_id, entity_id)

    version_service = QuestionPaperVersionService(db)
    version = await version_service.create_snapshot(
        institution_id, paper, change_reason=body.change_reason, actor_id=current_user.id
    )
    await db.commit()
    return QuestionPaperVersionRead.model_validate(version)
