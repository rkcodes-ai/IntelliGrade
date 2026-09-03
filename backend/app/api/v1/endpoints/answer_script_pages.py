"""
AnswerScriptPage browsing endpoints (read-only).

Read-only from the API's perspective — pages are written internally by
`app.tasks.ocr_tasks` during Stage 4/6 page-splitting via
`AnswerScriptPageService.create()`, never through this router. `GET ""`
supports filtering to one parent script via `?answer_script_id=`.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.answer_script_page import AnswerScriptPage
from app.schemas.answer_script_page import AnswerScriptPageRead
from app.schemas.pagination import Page, PageParams
from app.services.answer_script_page_service import AnswerScriptPageService

router = APIRouter(prefix="/answer-script-pages", tags=["Answer Script Pages"])


def _to_read(entity: AnswerScriptPage) -> AnswerScriptPageRead:
    return AnswerScriptPageRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[AnswerScriptPageRead],
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_SCRIPT_PAGES_READ))],
)
async def list_answer_script_pages(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    params: Annotated[PageParams, Depends()],
    answer_script_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[AnswerScriptPageRead]:
    service = AnswerScriptPageService(db)
    extra_filters: tuple[Any, ...] = ()
    if answer_script_id is not None:
        extra_filters = (AnswerScriptPage.answer_script_id == answer_script_id,)
    items, total = await service.list_paginated(institution_id, params, extra_filters=extra_filters)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/{entity_id}",
    response_model=AnswerScriptPageRead,
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_SCRIPT_PAGES_READ))],
)
async def get_answer_script_page(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> AnswerScriptPageRead:
    service = AnswerScriptPageService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)
