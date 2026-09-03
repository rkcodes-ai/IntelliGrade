"""
ExtractedQuestion browsing/verification endpoints (Module 06).

Rows are written internally by `app.tasks.official_document_tasks` during
the OCR/AI extraction pipeline, never through this router — there is no
`POST ""` and no `DELETE`; these rows live and die with their parent
`OfficialExamDocument`. `GET ""` supports filtering to one parent document
via `?document_id=`, mirroring `app/api/v1/endpoints/answer_script_pages.py`.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.extracted_question import ExtractedQuestion
from app.schemas.extracted_question import ExtractedQuestionRead, ExtractedQuestionUpdate
from app.schemas.pagination import Page, PageParams
from app.services.extracted_question_service import ExtractedQuestionService

router = APIRouter(prefix="/extracted-questions", tags=["Extracted Questions"])


def _to_read(entity: ExtractedQuestion) -> ExtractedQuestionRead:
    return ExtractedQuestionRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[ExtractedQuestionRead],
    dependencies=[Depends(require_permissions(PermissionCode.EXTRACTED_QUESTIONS_READ))],
)
async def list_extracted_questions(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    params: Annotated[PageParams, Depends()],
    document_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[ExtractedQuestionRead]:
    service = ExtractedQuestionService(db)
    extra_filters: tuple[Any, ...] = ()
    if document_id is not None:
        extra_filters = (ExtractedQuestion.document_id == document_id,)
    items, total = await service.list_paginated(institution_id, params, extra_filters=extra_filters)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/{entity_id}",
    response_model=ExtractedQuestionRead,
    dependencies=[Depends(require_permissions(PermissionCode.EXTRACTED_QUESTIONS_READ))],
)
async def get_extracted_question(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> ExtractedQuestionRead:
    service = ExtractedQuestionService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=ExtractedQuestionRead,
    dependencies=[Depends(require_permissions(PermissionCode.EXTRACTED_QUESTIONS_UPDATE))],
)
async def update_extracted_question(
    entity_id: uuid.UUID,
    body: ExtractedQuestionUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ExtractedQuestionRead:
    service = ExtractedQuestionService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/verify",
    response_model=ExtractedQuestionRead,
    dependencies=[Depends(require_permissions(PermissionCode.EXTRACTED_QUESTIONS_VERIFY))],
)
async def verify_extracted_question(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ExtractedQuestionRead:
    service = ExtractedQuestionService(db)
    entity = await service.verify(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)
