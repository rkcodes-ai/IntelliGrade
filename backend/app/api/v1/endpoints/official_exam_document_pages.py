"""
OfficialExamDocumentPage browsing endpoints (read-only).

Read-only from the API's perspective — pages are written internally by
`app.tasks.official_document_tasks` during page extraction/preprocessing
via `OfficialExamDocumentPageService.create()`, never through this
router. `GET ""` supports filtering to one parent document via
`?document_id=`.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.official_exam_document_page import OfficialExamDocumentPage
from app.schemas.official_exam_document_page import OfficialExamDocumentPageRead
from app.schemas.pagination import Page, PageParams
from app.services.official_exam_document_page_service import OfficialExamDocumentPageService

router = APIRouter(prefix="/official-exam-document-pages", tags=["Official Exam Document Pages"])


def _to_read(entity: OfficialExamDocumentPage) -> OfficialExamDocumentPageRead:
    return OfficialExamDocumentPageRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[OfficialExamDocumentPageRead],
    dependencies=[Depends(require_permissions(PermissionCode.OFFICIAL_EXAM_DOCUMENT_PAGES_READ))],
)
async def list_official_exam_document_pages(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    params: Annotated[PageParams, Depends()],
    document_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[OfficialExamDocumentPageRead]:
    service = OfficialExamDocumentPageService(db)
    extra_filters: tuple[Any, ...] = ()
    if document_id is not None:
        extra_filters = (OfficialExamDocumentPage.document_id == document_id,)
    items, total = await service.list_paginated(institution_id, params, extra_filters=extra_filters)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/{entity_id}",
    response_model=OfficialExamDocumentPageRead,
    dependencies=[Depends(require_permissions(PermissionCode.OFFICIAL_EXAM_DOCUMENT_PAGES_READ))],
)
async def get_official_exam_document_page(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> OfficialExamDocumentPageRead:
    service = OfficialExamDocumentPageService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)
