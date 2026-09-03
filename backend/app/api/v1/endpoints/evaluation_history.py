"""EvaluationHistory endpoints.

Deliberately narrow: only `GET ""`, `GET "/{id}"`, `POST ""`. There is no
`EVALUATION_HISTORY_UPDATE`/`DELETE` permission code (only CREATE/READ
exist — see `app/core/constants.py`), so unlike every other Assessment
Domain entity in this codebase there is intentionally no `GET "/deleted"`,
`PATCH`, `DELETE`, or `POST "/{id}/restore"` route here, and no
`import`/`export`/`bulk` skeleton routes either.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.evaluation_history import EvaluationHistory
from app.schemas.evaluation_history import EvaluationHistoryCreate, EvaluationHistoryRead
from app.schemas.pagination import Page, PageParams
from app.services.evaluation_history_service import EvaluationHistoryService

router = APIRouter(prefix="/evaluation-history", tags=["Evaluation History"])


def _to_read(entity: EvaluationHistory) -> EvaluationHistoryRead:
    return EvaluationHistoryRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[EvaluationHistoryRead],
    dependencies=[Depends(require_permissions(PermissionCode.EVALUATION_HISTORY_READ))],
)
async def list_evaluation_history(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[EvaluationHistoryRead]:
    service = EvaluationHistoryService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "",
    response_model=EvaluationHistoryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.EVALUATION_HISTORY_CREATE))],
)
async def create_evaluation_history(
    body: EvaluationHistoryCreate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> EvaluationHistoryRead:
    service = EvaluationHistoryService(db)
    entity = await service.create(institution_id, body, created_by=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=EvaluationHistoryRead,
    dependencies=[Depends(require_permissions(PermissionCode.EVALUATION_HISTORY_READ))],
)
async def get_evaluation_history(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> EvaluationHistoryRead:
    service = EvaluationHistoryService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)
