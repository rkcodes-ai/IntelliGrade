"""
Question approval decision browsing endpoints (read-only).

Per this entity's spec, only listing and single-row read are exposed here —
no `POST`/`PATCH`/`DELETE` route. Rows are inserted by
`QuestionApprovalService.create()`/`record()` (see
`app/services/question_approval_service.py`, including a note on the
follow-up integration with `QuestionService.approve()`/`reject()`), not
through this router.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.question_approval import QuestionApproval
from app.schemas.pagination import Page, PageParams
from app.schemas.question_approval import QuestionApprovalRead
from app.services.question_approval_service import QuestionApprovalService

router = APIRouter(prefix="/question-approvals", tags=["Question Approvals"])


def _to_read(entity: QuestionApproval) -> QuestionApprovalRead:
    return QuestionApprovalRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[QuestionApprovalRead],
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_APPROVALS_READ))],
)
async def list_question_approvals(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[QuestionApprovalRead]:
    service = QuestionApprovalService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/{entity_id}",
    response_model=QuestionApprovalRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_APPROVALS_READ))],
)
async def get_question_approval(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> QuestionApprovalRead:
    service = QuestionApprovalService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)
