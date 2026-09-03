"""QuestionPaperVersion browsing endpoints (read-only — creation is nested
under `POST /question-papers/{id}/versions`, see
`app/api/v1/endpoints/question_papers.py`)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.question_paper_version import QuestionPaperVersion
from app.schemas.pagination import Page, PageParams
from app.schemas.question_paper_version import QuestionPaperVersionRead
from app.services.question_paper_version_service import QuestionPaperVersionService

router = APIRouter(prefix="/question-paper-versions", tags=["Question Paper Versions"])


def _to_read(entity: QuestionPaperVersion) -> QuestionPaperVersionRead:
    return QuestionPaperVersionRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[QuestionPaperVersionRead],
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPER_VERSIONS_READ))],
)
async def list_question_paper_versions(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[QuestionPaperVersionRead]:
    service = QuestionPaperVersionService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/{entity_id}",
    response_model=QuestionPaperVersionRead,
    dependencies=[Depends(require_permissions(PermissionCode.QUESTION_PAPER_VERSIONS_READ))],
)
async def get_question_paper_version(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> QuestionPaperVersionRead:
    service = QuestionPaperVersionService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)
