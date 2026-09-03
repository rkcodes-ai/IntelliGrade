"""QuestionPaperQuestionMapping management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import AppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.question_paper_question_mapping import QuestionPaperQuestionMapping
from app.schemas.pagination import Page, PageParams
from app.schemas.question_paper_question_mapping import (
    QuestionPaperQuestionMappingCreate,
    QuestionPaperQuestionMappingRead,
    QuestionPaperQuestionMappingUpdate,
)
from app.services.question_paper_question_mapping_service import (
    QuestionPaperQuestionMappingService,
)

router = APIRouter(
    prefix="/question-paper-question-mappings", tags=["Question Paper Question Mappings"]
)


def _to_read(entity: QuestionPaperQuestionMapping) -> QuestionPaperQuestionMappingRead:
    return QuestionPaperQuestionMappingRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[QuestionPaperQuestionMappingRead],
    dependencies=[
        Depends(require_permissions(PermissionCode.QUESTION_PAPER_QUESTION_MAPPINGS_READ))
    ],
)
async def list_question_paper_question_mappings(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[QuestionPaperQuestionMappingRead]:
    service = QuestionPaperQuestionMappingService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[QuestionPaperQuestionMappingRead],
    dependencies=[
        Depends(require_permissions(PermissionCode.QUESTION_PAPER_QUESTION_MAPPINGS_DELETE))
    ],
)
async def list_deleted_question_paper_question_mappings(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[QuestionPaperQuestionMappingRead]:
    service = QuestionPaperQuestionMappingService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[
        Depends(require_permissions(PermissionCode.QUESTION_PAPER_QUESTION_MAPPINGS_CREATE))
    ],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_question_paper_question_mappings() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 04 skeleton only."}


@router.get(
    "/export",
    dependencies=[
        Depends(require_permissions(PermissionCode.QUESTION_PAPER_QUESTION_MAPPINGS_READ))
    ],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_question_paper_question_mappings() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 04 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_permissions(PermissionCode.QUESTION_PAPER_QUESTION_MAPPINGS_CREATE))
    ],
    summary="Bulk-create question paper question mappings, collecting per-item errors",
)
async def bulk_create_question_paper_question_mappings(
    body: list[QuestionPaperQuestionMappingCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, object]:
    service = QuestionPaperQuestionMappingService(db)
    created = 0
    errors: list[dict[str, object]] = []
    for index, item in enumerate(body):
        try:
            await service.create(institution_id, item, created_by=current_user.id)
            created += 1
        except AppError as exc:
            errors.append(
                {"index": index, "question_id": str(item.question_id), "error": exc.message}
            )
    await db.commit()
    return {"created": created, "errors": errors}


@router.post(
    "",
    response_model=QuestionPaperQuestionMappingRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_permissions(PermissionCode.QUESTION_PAPER_QUESTION_MAPPINGS_CREATE))
    ],
)
async def create_question_paper_question_mapping(
    body: QuestionPaperQuestionMappingCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionPaperQuestionMappingRead:
    service = QuestionPaperQuestionMappingService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=QuestionPaperQuestionMappingRead,
    dependencies=[
        Depends(require_permissions(PermissionCode.QUESTION_PAPER_QUESTION_MAPPINGS_READ))
    ],
)
async def get_question_paper_question_mapping(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> QuestionPaperQuestionMappingRead:
    service = QuestionPaperQuestionMappingService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=QuestionPaperQuestionMappingRead,
    dependencies=[
        Depends(require_permissions(PermissionCode.QUESTION_PAPER_QUESTION_MAPPINGS_UPDATE))
    ],
)
async def update_question_paper_question_mapping(
    entity_id: uuid.UUID,
    body: QuestionPaperQuestionMappingUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionPaperQuestionMappingRead:
    service = QuestionPaperQuestionMappingService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(require_permissions(PermissionCode.QUESTION_PAPER_QUESTION_MAPPINGS_DELETE))
    ],
)
async def delete_question_paper_question_mapping(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = QuestionPaperQuestionMappingService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=QuestionPaperQuestionMappingRead,
    dependencies=[
        Depends(require_permissions(PermissionCode.QUESTION_PAPER_QUESTION_MAPPINGS_DELETE))
    ],
)
async def restore_question_paper_question_mapping(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionPaperQuestionMappingRead:
    service = QuestionPaperQuestionMappingService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
