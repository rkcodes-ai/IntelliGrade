"""ReportJob endpoints — background report generation (Module 07, Feature 8).
See ADR-045.

`POST ""` enqueues `app.tasks.report_tasks.generate_report_task` via
`_enqueue_report_generation` below — best-effort, mirroring
`app/api/v1/endpoints/official_exam_documents.py`'s dispatch helper
exactly (an unreachable broker shouldn't turn a successful request into
a 500; the job is simply left `pending`).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import PermissionCode
from app.core.exceptions import ValidationAppError
from app.core.logging import get_logger
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.report_job import ReportJob
from app.schemas.pagination import Page, PageParams
from app.schemas.report_job import ReportGenerateRequest, ReportJobRead
from app.services.report_service import ReportService
from app.services.storage_service import StorageService

router = APIRouter(prefix="/reports", tags=["Reports"])
logger = get_logger(__name__)


def _enqueue_report_generation(report_job_id: uuid.UUID) -> None:
    try:
        from app.tasks.report_tasks import generate_report_task

        generate_report_task.delay(str(report_job_id))
    except Exception as exc:  # noqa: BLE001 - broker connectivity is inherently unpredictable
        logger.warning(
            "report_generation_enqueue_failed", report_job_id=str(report_job_id), error=str(exc)
        )


def _to_read(entity: ReportJob) -> ReportJobRead:
    return ReportJobRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[ReportJobRead],
    dependencies=[Depends(require_permissions(PermissionCode.REPORTS_READ))],
)
async def list_reports(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[ReportJobRead]:
    service = ReportService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/{entity_id}",
    response_model=ReportJobRead,
    dependencies=[Depends(require_permissions(PermissionCode.REPORTS_READ))],
)
async def get_report(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> ReportJobRead:
    service = ReportService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.post(
    "",
    response_model=ReportJobRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.REPORTS_GENERATE))],
)
async def generate_report(
    body: ReportGenerateRequest,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> ReportJobRead:
    service = ReportService(db)
    job = await service.create_job(
        institution_id,
        report_type=body.report_type,
        format=body.format,
        parameters=body.parameters,
        actor_id=current_user.id,
    )
    await db.commit()
    _enqueue_report_generation(job.id)
    return _to_read(job)


@router.get(
    "/{entity_id}/download",
    dependencies=[Depends(require_permissions(PermissionCode.REPORTS_READ))],
)
async def download_report(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> dict[str, str]:
    """Returns a short-lived presigned URL rather than streaming bytes
    through this API process directly — same convention as Module 06's
    `OfficialExamDocument` download endpoint."""
    service = ReportService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    if entity.status != "completed" or not entity.storage_key:
        raise ValidationAppError("This report is not ready for download yet.")
    storage = StorageService()
    url = await storage.presigned_get_url(entity.storage_key)
    return {"url": url}
