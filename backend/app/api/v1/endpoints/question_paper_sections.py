"""QuestionPaperSection management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import AppError
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.question_paper_section import QuestionPaperSection
from app.schemas.pagination import Page, PageParams
from app.schemas.question_paper_section import (
    QuestionPaperSectionCreate,
    QuestionPaperSectionRead,
    QuestionPaperSectionUpdate,
)
from app.services.question_paper_section_service import QuestionPaperSectionService

router = APIRouter(prefix="/question-paper-sections", tags=["Question Paper Sections"])


def _to_read(entity: QuestionPaperSection) -> QuestionPaperSectionRead:
    return QuestionPaperSectionRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[QuestionPaperSectionRead],
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPER_SECTIONS_READ))],
)
async def list_question_paper_sections(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[QuestionPaperSectionRead]:
    service = QuestionPaperSectionService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[QuestionPaperSectionRead],
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPER_SECTIONS_DELETE))],
)
async def list_deleted_question_paper_sections(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[QuestionPaperSectionRead]:
    service = QuestionPaperSectionService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPER_SECTIONS_CREATE))],
    summary="Bulk import (CSV/Excel) — skeleton, not yet implemented",
)
async def import_question_paper_sections() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a Module 04 skeleton only."}


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPER_SECTIONS_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_question_paper_sections() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a Module 04 skeleton only."}


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPER_SECTIONS_CREATE))],
    summary="Bulk-create question paper sections, collecting per-item errors instead of aborting",
)
async def bulk_create_question_paper_sections(
    body: list[QuestionPaperSectionCreate],
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> dict[str, object]:
    service = QuestionPaperSectionService(db)
    created = 0
    errors: list[dict[str, object]] = []
    for index, item in enumerate(body):
        try:
            await service.create(institution_id, item, created_by=current_user.id)
            created += 1
        except AppError as exc:
            errors.append({"index": index, "name": item.name, "error": exc.message})
    await db.commit()
    return {"created": created, "errors": errors}


@router.post(
    "",
    response_model=QuestionPaperSectionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPER_SECTIONS_CREATE))],
)
async def create_question_paper_section(
    body: QuestionPaperSectionCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionPaperSectionRead:
    service = QuestionPaperSectionService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=QuestionPaperSectionRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPER_SECTIONS_READ))],
)
async def get_question_paper_section(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> QuestionPaperSectionRead:
    service = QuestionPaperSectionService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=QuestionPaperSectionRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPER_SECTIONS_UPDATE))],
)
async def update_question_paper_section(
    entity_id: uuid.UUID,
    body: QuestionPaperSectionUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionPaperSectionRead:
    service = QuestionPaperSectionService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPER_SECTIONS_DELETE))],
)
async def delete_question_paper_section(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = QuestionPaperSectionService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=QuestionPaperSectionRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPER_SECTIONS_DELETE))],
)
async def restore_question_paper_section(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> QuestionPaperSectionRead:
    service = QuestionPaperSectionService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
