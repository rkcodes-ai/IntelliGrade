"""
AnswerEvaluation endpoints — triggering AI evaluation and the two Teacher
Review actions (confirm/override, ADR-040). `POST ""` runs
`AnswerEvaluationService.evaluate_question()` synchronously (unlike the
OCR/ingestion pipelines, one evaluation call is fast — a local
lexical/statistical computation, not a network round-trip — so no Celery
task is needed here; see `docs/ai-evaluation-guide.md`).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.answer_evaluation import AnswerEvaluation
from app.schemas.answer_evaluation import (
    AnswerEvaluationOverride,
    AnswerEvaluationRead,
    AnswerEvaluationReject,
    AnswerEvaluationTrigger,
)
from app.schemas.pagination import Page, PageParams
from app.services.answer_evaluation_service import AnswerEvaluationService

router = APIRouter(prefix="/answer-evaluations", tags=["Answer Evaluations"])


def _to_read(entity: AnswerEvaluation) -> AnswerEvaluationRead:
    return AnswerEvaluationRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[AnswerEvaluationRead],
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_EVALUATIONS_READ))],
)
async def list_answer_evaluations(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AnswerEvaluationRead]:
    service = AnswerEvaluationService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/{entity_id}",
    response_model=AnswerEvaluationRead,
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_EVALUATIONS_READ))],
)
async def get_answer_evaluation(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> AnswerEvaluationRead:
    service = AnswerEvaluationService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.post(
    "",
    response_model=AnswerEvaluationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_EVALUATIONS_CREATE))],
)
async def trigger_answer_evaluation(
    body: AnswerEvaluationTrigger,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AnswerEvaluationRead:
    service = AnswerEvaluationService(db)
    entity = await service.evaluate_question(
        institution_id,
        exam_session_id=body.exam_session_id,
        extracted_question_id=body.extracted_question_id,
        actor_id=current_user.id,
    )
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/confirm",
    response_model=AnswerEvaluationRead,
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_EVALUATIONS_CONFIRM))],
)
async def confirm_answer_evaluation(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AnswerEvaluationRead:
    service = AnswerEvaluationService(db)
    entity = await service.confirm(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/override",
    response_model=AnswerEvaluationRead,
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_EVALUATIONS_OVERRIDE))],
)
async def override_answer_evaluation(
    entity_id: uuid.UUID,
    body: AnswerEvaluationOverride,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AnswerEvaluationRead:
    service = AnswerEvaluationService(db)
    entity = await service.override(institution_id, entity_id, body, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/reject",
    response_model=AnswerEvaluationRead,
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_EVALUATIONS_REJECT))],
)
async def reject_answer_evaluation(
    entity_id: uuid.UUID,
    body: AnswerEvaluationReject,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AnswerEvaluationRead:
    service = AnswerEvaluationService(db)
    entity = await service.reject(institution_id, entity_id, body, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/rerun",
    response_model=AnswerEvaluationRead,
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_EVALUATIONS_RERUN))],
)
async def rerun_answer_evaluation(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AnswerEvaluationRead:
    service = AnswerEvaluationService(db)
    entity = await service.rerun(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)
