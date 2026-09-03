"""
AIReferenceAnswer endpoints — generating, listing, approving, rejecting,
and regenerating AI reference answers (AI Reference Answer Builder
milestone).

`POST ""` runs `ReferenceAnswerService.generate()` **synchronously**,
same tradeoff `answer_evaluations.py` already makes for the sibling
evaluation-trigger endpoint: with the default `lexical_heuristic`
provider this is a fast local computation, and even a real OpenAI/
Anthropic call (typically a few seconds) is tolerable for a teacher-
triggered admin action, not a high-frequency public endpoint. A real
Celery task (`app.tasks.reference_answer_tasks.
generate_reference_answer_task`) exists and is registered for anyone
wanting to enqueue generation asynchronously instead (e.g. a future
bulk-regenerate-all-questions feature) — Phase 12's "reuse existing
background-task conventions" requirement is satisfied by that task
existing and being real, not by forcing every caller through a queue.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.ai_reference_answer import AIReferenceAnswer
from app.schemas.ai_reference_answer import (
    AIReferenceAnswerGenerate,
    AIReferenceAnswerRead,
    AIReferenceAnswerReject,
)
from app.schemas.pagination import Page, PageParams
from app.services.ai_reference_answer_service import ReferenceAnswerService

router = APIRouter(prefix="/ai-reference-answers", tags=["AI Reference Answers"])


def _to_read(entity: AIReferenceAnswer) -> AIReferenceAnswerRead:
    return AIReferenceAnswerRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[AIReferenceAnswerRead],
    dependencies=[Depends(require_permissions(PermissionCode.AI_REFERENCE_ANSWERS_READ))],
)
async def list_ai_reference_answers(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AIReferenceAnswerRead]:
    service = ReferenceAnswerService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/{entity_id}",
    response_model=AIReferenceAnswerRead,
    dependencies=[Depends(require_permissions(PermissionCode.AI_REFERENCE_ANSWERS_READ))],
)
async def get_ai_reference_answer(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> AIReferenceAnswerRead:
    service = ReferenceAnswerService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.get(
    "/by-question/{extracted_question_id}/current",
    response_model=AIReferenceAnswerRead | None,
    dependencies=[Depends(require_permissions(PermissionCode.AI_REFERENCE_ANSWERS_READ))],
)
async def get_current_ai_reference_answer(
    extracted_question_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> AIReferenceAnswerRead | None:
    service = ReferenceAnswerService(db)
    entity = await service.get_current_for_question(institution_id, extracted_question_id)
    return _to_read(entity) if entity is not None else None


@router.get(
    "/by-question/{extracted_question_id}/versions",
    response_model=list[AIReferenceAnswerRead],
    dependencies=[Depends(require_permissions(PermissionCode.AI_REFERENCE_ANSWERS_READ))],
)
async def list_ai_reference_answer_versions(
    extracted_question_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> list[AIReferenceAnswerRead]:
    service = ReferenceAnswerService(db)
    versions = await service.list_versions(institution_id, extracted_question_id)
    return [_to_read(v) for v in versions]


@router.post(
    "",
    response_model=AIReferenceAnswerRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.AI_REFERENCE_ANSWERS_CREATE))],
)
async def generate_ai_reference_answer(
    body: AIReferenceAnswerGenerate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AIReferenceAnswerRead:
    service = ReferenceAnswerService(db)
    entity = await service.generate(
        institution_id,
        body.extracted_question_id,
        actor_id=current_user.id,
        force=body.force,
    )
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/approve",
    response_model=AIReferenceAnswerRead,
    dependencies=[Depends(require_permissions(PermissionCode.AI_REFERENCE_ANSWERS_APPROVE))],
)
async def approve_ai_reference_answer(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AIReferenceAnswerRead:
    service = ReferenceAnswerService(db)
    entity = await service.approve(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/reject",
    response_model=AIReferenceAnswerRead,
    dependencies=[Depends(require_permissions(PermissionCode.AI_REFERENCE_ANSWERS_REJECT))],
)
async def reject_ai_reference_answer(
    entity_id: uuid.UUID,
    body: AIReferenceAnswerReject,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AIReferenceAnswerRead:
    service = ReferenceAnswerService(db)
    entity = await service.reject(institution_id, entity_id, body, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.post(
    "/by-question/{extracted_question_id}/regenerate",
    response_model=AIReferenceAnswerRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.AI_REFERENCE_ANSWERS_REGENERATE))],
)
async def regenerate_ai_reference_answer(
    extracted_question_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AIReferenceAnswerRead:
    service = ReferenceAnswerService(db)
    entity = await service.regenerate(
        institution_id, extracted_question_id, actor_id=current_user.id
    )
    await db.commit()
    return _to_read(entity)
