"""
OfficialExamDocument upload/management endpoints — the entry point of the
Module 06 ingestion pipeline (Question Paper / Model Answer / Mark Scheme
PDFs uploaded by the Exam Cell/Faculty). `POST ""` is the only endpoint
that differs from the standard CRUD shape (multipart file upload, not a
JSON body) — see `OfficialExamDocumentService.upload()` for the actual
validate -> persist -> store orchestration.

Every path that leaves a document ready for processing (`upload`, `retry`)
enqueues `app.tasks.official_document_tasks.process_official_document_task`
via `_enqueue_official_document_pipeline` below — best-effort, mirroring
`app/api/v1/endpoints/answer_scripts.py`'s `_enqueue_ocr_pipeline` exactly
(ADR-036: a new, parallel dispatch helper, not a change to that one).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import ValidationAppError
from app.core.logging import get_logger
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.official_exam_document import OfficialExamDocument
from app.schemas.official_exam_document import OfficialExamDocumentRead, OfficialExamDocumentUpdate
from app.schemas.pagination import Page, PageParams
from app.services.official_exam_document_service import OfficialExamDocumentService
from app.services.storage_service import StorageService

router = APIRouter(prefix="/official-exam-documents", tags=["Official Exam Documents"])
logger = get_logger(__name__)


def _enqueue_official_document_pipeline(document_id: uuid.UUID) -> None:
    """Fire-and-forget dispatch onto the Celery/Redis broker. Swallows any
    broker-connection failure (logging a warning instead) — an unreachable
    Redis shouldn't turn a successful upload into a 500; the document is
    simply left for a manual `/retry` once the broker is back."""
    try:
        from app.tasks.official_document_tasks import process_official_document_task

        process_official_document_task.delay(str(document_id))
    except Exception as exc:  # noqa: BLE001 - broker connectivity is inherently unpredictable
        logger.warning(
            "official_document_pipeline_enqueue_failed",
            document_id=str(document_id),
            error=str(exc),
        )


def _to_read(entity: OfficialExamDocument) -> OfficialExamDocumentRead:
    return OfficialExamDocumentRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[OfficialExamDocumentRead],
    dependencies=[Depends(require_permissions(PermissionCode.OFFICIAL_EXAM_DOCUMENTS_READ))],
)
async def list_official_exam_documents(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[OfficialExamDocumentRead]:
    service = OfficialExamDocumentService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[OfficialExamDocumentRead],
    dependencies=[Depends(require_permissions(PermissionCode.OFFICIAL_EXAM_DOCUMENTS_DELETE))],
)
async def list_deleted_official_exam_documents(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[OfficialExamDocumentRead]:
    service = OfficialExamDocumentService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.post(
    "",
    response_model=OfficialExamDocumentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.OFFICIAL_EXAM_DOCUMENTS_CREATE))],
)
async def upload_official_exam_document(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
    exam_id: Annotated[uuid.UUID, Form()],
    document_type: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    allow_duplicate: Annotated[bool, Form()] = False,
) -> OfficialExamDocumentRead:
    service = OfficialExamDocumentService(db)
    file_bytes = await file.read()
    entity = await service.upload(
        institution_id,
        exam_id=exam_id,
        document_type=document_type,
        original_filename=file.filename or "upload",
        mime_type=file.content_type or "application/octet-stream",
        file_bytes=file_bytes,
        uploaded_by=current_user.id,
        allow_duplicate=allow_duplicate,
    )
    await db.commit()
    _enqueue_official_document_pipeline(entity.id)
    return _to_read(entity)


@router.get(
    "/{entity_id}",
    response_model=OfficialExamDocumentRead,
    dependencies=[Depends(require_permissions(PermissionCode.OFFICIAL_EXAM_DOCUMENTS_READ))],
)
async def get_official_exam_document(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> OfficialExamDocumentRead:
    service = OfficialExamDocumentService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.get(
    "/{entity_id}/download",
    dependencies=[Depends(require_permissions(PermissionCode.OFFICIAL_EXAM_DOCUMENTS_READ))],
)
async def download_official_exam_document(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> dict[str, str]:
    """Returns a short-lived presigned URL for the original uploaded file
    rather than streaming bytes through this API process directly."""
    service = OfficialExamDocumentService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    if not entity.storage_key:
        raise ValidationAppError("This document has no stored file yet.")
    storage = StorageService()
    url = await storage.presigned_get_url(entity.storage_key)
    return {"url": url}


@router.patch(
    "/{entity_id}",
    response_model=OfficialExamDocumentRead,
    dependencies=[Depends(require_permissions(PermissionCode.OFFICIAL_EXAM_DOCUMENTS_UPDATE))],
)
async def update_official_exam_document(
    entity_id: uuid.UUID,
    body: OfficialExamDocumentUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> OfficialExamDocumentRead:
    service = OfficialExamDocumentService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(entity, field, value)
    entity.updated_by = current_user.id
    await db.flush()
    await db.refresh(entity)
    await db.commit()
    return _to_read(entity)


@router.post(
    "/{entity_id}/retry",
    response_model=OfficialExamDocumentRead,
    dependencies=[Depends(require_permissions(PermissionCode.OFFICIAL_EXAM_DOCUMENTS_RETRY))],
)
async def retry_official_exam_document(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> OfficialExamDocumentRead:
    service = OfficialExamDocumentService(db)
    entity = await service.request_retry(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    _enqueue_official_document_pipeline(entity.id)
    return _to_read(entity)


@router.post(
    "/{entity_id}/cancel",
    response_model=OfficialExamDocumentRead,
    dependencies=[Depends(require_permissions(PermissionCode.OFFICIAL_EXAM_DOCUMENTS_CANCEL))],
)
async def cancel_official_exam_document(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> OfficialExamDocumentRead:
    service = OfficialExamDocumentService(db)
    entity = await service.request_cancel(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.OFFICIAL_EXAM_DOCUMENTS_DELETE))],
)
async def delete_official_exam_document(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = OfficialExamDocumentService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.OFFICIAL_EXAM_DOCUMENT_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=OfficialExamDocumentRead,
    dependencies=[Depends(require_permissions(PermissionCode.OFFICIAL_EXAM_DOCUMENTS_DELETE))],
)
async def restore_official_exam_document(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> OfficialExamDocumentRead:
    service = OfficialExamDocumentService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
