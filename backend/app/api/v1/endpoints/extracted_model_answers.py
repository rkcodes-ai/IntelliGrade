"""
ExtractedModelAnswer browsing/verification endpoints (Module 06).

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
from app.models.extracted_model_answer import ExtractedModelAnswer
from app.schemas.extracted_model_answer import ExtractedModelAnswerRead, ExtractedModelAnswerUpdate
from app.schemas.pagination import Page, PageParams
from app.services.extracted_model_answer_service import ExtractedModelAnswerService

router = APIRouter(prefix="/extracted-model-answers", tags=["Extracted Model Answers"])


def _to_read(entity: ExtractedModelAnswer) -> ExtractedModelAnswerRead:
    return ExtractedModelAnswerRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[ExtractedModelAnswerRead],
    dependencies=[Depends(require_permissions(PermissionCode.EXTRACTED_MODEL_ANSWERS_READ))],
)
async def list_extracted_model_answers(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    params: Annotated[PageParams, Depends()],
    document_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[ExtractedModelAnswerRead]:
    service = ExtractedModelAnswerService(db)
    extra_filters: tuple[Any, ...] = ()
    if document_id is not None:
        extra_filters = (ExtractedModelAnswer.document_id == document_id,)
    items, total = await service.list_paginated(institution_id, params, extra_filters=extra_filters)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/{entity_id}",
    response_model=ExtractedModelAnswerRead,
    dependencies=[Depends(require_permissions(PermissionCode.EXTRACTED_MODEL_ANSWERS_READ))],
)
async def get_extracted_model_answer(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> ExtractedModelAnswerRead:
    service = ExtractedModelAnswerService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=ExtractedModelAnswerRead,
    dependencies=[Depends(require_permissions(PermissionCode.EXTRACTED_MODEL_ANSWERS_UPDATE))],
)
async def update_extracted_model_answer(
    entity_id: uuid.UUID,
    body: ExtractedModelAnswerUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ExtractedModelAnswerRead:
    service = ExtractedModelAnswerService(db)
    entity = await service.update(institution_id, entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/verify",
    response_model=ExtractedModelAnswerRead,
    dependencies=[Depends(require_permissions(PermissionCode.EXTRACTED_MODEL_ANSWERS_VERIFY))],
)
async def verify_extracted_model_answer(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ExtractedModelAnswerRead:
    service = ExtractedModelAnswerService(db)
    entity = await service.verify(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)
