"""ExamResult endpoints — Result Finalization & Locking (Module 07, ADR-042).

`POST /finalize-student|finalize-exam|finalize-batch` cover Feature 4's
three finalization granularities; `/approve|/lock|/unlock|/publish` are
Feature 5's validated state-machine transitions; the `/bulk/*` actions
cover Feature 11's bulk approval/lock/publish.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.exam_result import ExamResult
from app.schemas.exam_result import (
    BulkActionResult,
    BulkExamRequest,
    ExamResultRead,
    FinalizeBatchRequest,
    FinalizeExamRequest,
    FinalizeStudentRequest,
)
from app.schemas.pagination import Page, PageParams
from app.services.exam_result_service import ExamResultService

router = APIRouter(prefix="/exam-results", tags=["Exam Results"])


def _to_read(entity: ExamResult) -> ExamResultRead:
    return ExamResultRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[ExamResultRead],
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_RESULTS_READ))],
)
async def list_exam_results(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[ExamResultRead]:
    service = ExamResultService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/{entity_id}",
    response_model=ExamResultRead,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_RESULTS_READ))],
)
async def get_exam_result(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> ExamResultRead:
    service = ExamResultService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.post(
    "/finalize-student",
    response_model=ExamResultRead,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_RESULTS_FINALIZE))],
)
async def finalize_student_result(
    body: FinalizeStudentRequest,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ExamResultRead:
    service = ExamResultService(db)
    entity = await service.finalize_student(
        institution_id, body.exam_session_id, actor_id=current_user.id
    )
    await db.commit()
    return _to_read(entity)


@router.post(
    "/finalize-exam",
    response_model=BulkActionResult,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_RESULTS_FINALIZE))],
)
async def finalize_exam_results(
    body: FinalizeExamRequest,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> BulkActionResult:
    service = ExamResultService(db)
    result = await service.finalize_exam(institution_id, body.exam_id, actor_id=current_user.id)
    await db.commit()
    return result


@router.post(
    "/finalize-batch",
    response_model=BulkActionResult,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_RESULTS_FINALIZE))],
)
async def finalize_batch_results(
    body: FinalizeBatchRequest,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> BulkActionResult:
    service = ExamResultService(db)
    result = await service.finalize_batch(
        institution_id, body.exam_id, body.batch_id, actor_id=current_user.id
    )
    await db.commit()
    return result


@router.post(
    "/bulk/approve",
    response_model=BulkActionResult,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_RESULTS_APPROVE))],
)
async def bulk_approve_exam_results(
    body: BulkExamRequest,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> BulkActionResult:
    service = ExamResultService(db)
    result = await service.bulk_transition(
        institution_id, body.exam_id, action="approve", actor_id=current_user.id
    )
    await db.commit()
    return result


@router.post(
    "/bulk/lock",
    response_model=BulkActionResult,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_RESULTS_LOCK))],
)
async def bulk_lock_exam_results(
    body: BulkExamRequest,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> BulkActionResult:
    service = ExamResultService(db)
    result = await service.bulk_transition(
        institution_id, body.exam_id, action="lock", actor_id=current_user.id
    )
    await db.commit()
    return result


@router.post(
    "/bulk/publish",
    response_model=BulkActionResult,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_RESULTS_PUBLISH))],
)
async def bulk_publish_exam_results(
    body: BulkExamRequest,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> BulkActionResult:
    service = ExamResultService(db)
    result = await service.bulk_transition(
        institution_id, body.exam_id, action="publish", actor_id=current_user.id
    )
    await db.commit()
    return result


@router.post(
    "/{entity_id}/approve",
    response_model=ExamResultRead,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_RESULTS_APPROVE))],
)
async def approve_exam_result(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ExamResultRead:
    service = ExamResultService(db)
    entity = await service.approve(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/lock",
    response_model=ExamResultRead,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_RESULTS_LOCK))],
)
async def lock_exam_result(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ExamResultRead:
    service = ExamResultService(db)
    entity = await service.lock(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/unlock",
    response_model=ExamResultRead,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_RESULTS_UNLOCK))],
)
async def unlock_exam_result(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ExamResultRead:
    service = ExamResultService(db)
    entity = await service.unlock(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/publish",
    response_model=ExamResultRead,
    dependencies=[Depends(require_permissions(PermissionCode.EXAM_RESULTS_PUBLISH))],
)
async def publish_exam_result(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ExamResultRead:
    service = ExamResultService(db)
    entity = await service.publish(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)
