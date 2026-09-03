"""
AnswerScript upload/management endpoints — the entry point of the OCR
pipeline. `POST ""` and `POST "/bulk"` are the only endpoints in this
module that differ from the standard CRUD shape (multipart file upload,
not a JSON body) — see `AnswerScriptService.upload()` for the actual
validate -> persist -> store orchestration.

Every path that leaves a script ready for processing (`upload`, `bulk
upload`, `retry`) enqueues `app.tasks.ocr_tasks.process_answer_script_task`
via `_enqueue_ocr_pipeline` below. Enqueueing is best-effort: if the Redis
broker is unreachable, the script simply stays in `"stored"`/`"ocr_queued"`
status rather than the request failing — see that helper's docstring.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import AuditAction, PermissionCode
from app.core.exceptions import ConflictError, ValidationAppError
from app.core.logging import get_logger
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.answer_script import AnswerScript
from app.schemas.answer_script import AnswerScriptRead, AnswerScriptUpdate
from app.schemas.pagination import Page, PageParams
from app.services.answer_script_service import AnswerScriptService
from app.services.storage_service import StorageService

router = APIRouter(prefix="/answer-scripts", tags=["Answer Scripts"])
logger = get_logger(__name__)


def _enqueue_ocr_pipeline(answer_script_id: uuid.UUID) -> None:
    """Fire-and-forget dispatch onto the Celery/Redis broker. Deliberately
    swallows any broker-connection failure (logging a warning instead) —
    an unreachable Redis shouldn't turn a successful upload into a 500;
    the script is simply left for a manual `/retry` once the broker is
    back, or for whichever process eventually calls this again."""
    try:
        from app.tasks.ocr_tasks import process_answer_script_task

        process_answer_script_task.delay(str(answer_script_id))
    except Exception as exc:  # noqa: BLE001 - broker connectivity is inherently unpredictable
        logger.warning(
            "ocr_pipeline_enqueue_failed", answer_script_id=str(answer_script_id), error=str(exc)
        )


def _to_read(entity: AnswerScript) -> AnswerScriptRead:
    return AnswerScriptRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[AnswerScriptRead],
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_SCRIPTS_READ))],
)
async def list_answer_scripts(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AnswerScriptRead]:
    service = AnswerScriptService(db)
    items, total = await service.list_paginated(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/deleted",
    response_model=Page[AnswerScriptRead],
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_SCRIPTS_DELETE))],
)
async def list_deleted_answer_scripts(
    db: DbSession, institution_id: CurrentInstitutionDep, params: Annotated[PageParams, Depends()]
) -> Page[AnswerScriptRead]:
    service = AnswerScriptService(db)
    items, total = await service.list_deleted(institution_id, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/export",
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_SCRIPTS_READ))],
    summary="Bulk export (CSV/Excel) — skeleton, not yet implemented",
)
async def export_answer_scripts() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk export is a documented skeleton only."}


@router.post(
    "",
    response_model=AnswerScriptRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_SCRIPTS_CREATE))],
)
async def upload_answer_script(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
    exam_session_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
    allow_duplicate: Annotated[bool, Form()] = False,
) -> AnswerScriptRead:
    service = AnswerScriptService(db)
    file_bytes = await file.read()
    entity = await service.upload(
        institution_id,
        exam_session_id=exam_session_id,
        original_filename=file.filename or "upload",
        mime_type=file.content_type or "application/octet-stream",
        file_bytes=file_bytes,
        uploaded_by=current_user.id,
        allow_duplicate=allow_duplicate,
    )
    await db.commit()
    _enqueue_ocr_pipeline(entity.id)
    return _to_read(entity)


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_SCRIPTS_CREATE))],
    summary="Bulk-upload multiple answer scripts, collecting per-item errors",
)
async def bulk_upload_answer_scripts(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
    exam_session_id: Annotated[uuid.UUID, Form()],
    files: Annotated[list[UploadFile], File()],
) -> dict[str, object]:
    service = AnswerScriptService(db)
    created = 0
    errors: list[dict[str, object]] = []

    uploaded_ids: list[uuid.UUID] = []
    for index, upload in enumerate(files):
        try:
            file_bytes = await upload.read()
            entity = await service.upload(
                institution_id,
                exam_session_id=exam_session_id,
                original_filename=upload.filename or f"upload-{index}",
                mime_type=upload.content_type or "application/octet-stream",
                file_bytes=file_bytes,
                uploaded_by=current_user.id,
            )
            uploaded_ids.append(entity.id)
            created += 1
        except (ConflictError, ValidationAppError) as exc:
            errors.append({"index": index, "filename": upload.filename, "error": exc.message})

    await db.commit()
    for uploaded_id in uploaded_ids:
        _enqueue_ocr_pipeline(uploaded_id)
    return {"created": created, "errors": errors}


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_SCRIPTS_CREATE))],
    summary="Bulk import from an external source — skeleton, not yet implemented",
)
async def import_answer_scripts() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Bulk import is a documented skeleton only."}


@router.get(
    "/{entity_id}",
    response_model=AnswerScriptRead,
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_SCRIPTS_READ))],
)
async def get_answer_script(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> AnswerScriptRead:
    service = AnswerScriptService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    return _to_read(entity)


@router.get(
    "/{entity_id}/download",
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_SCRIPTS_READ))],
)
async def download_answer_script(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> dict[str, str]:
    """Returns a short-lived presigned URL for the original uploaded file
    rather than streaming bytes through this API process directly."""
    service = AnswerScriptService(db)
    entity = await service.get_by_id(institution_id, entity_id)
    if not entity.storage_key:
        raise ValidationAppError("This answer script has no stored file yet.")
    storage = StorageService()
    url = await storage.presigned_get_url(entity.storage_key)
    return {"url": url}


@router.patch(
    "/{entity_id}",
    response_model=AnswerScriptRead,
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_SCRIPTS_UPDATE))],
)
async def update_answer_script(
    entity_id: uuid.UUID,
    body: AnswerScriptUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AnswerScriptRead:
    service = AnswerScriptService(db)
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
    response_model=AnswerScriptRead,
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_SCRIPTS_RETRY))],
)
async def retry_answer_script(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AnswerScriptRead:
    service = AnswerScriptService(db)
    entity = await service.request_retry(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    _enqueue_ocr_pipeline(entity.id)
    return _to_read(entity)


@router.post(
    "/{entity_id}/cancel",
    response_model=AnswerScriptRead,
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_SCRIPTS_CANCEL))],
)
async def cancel_answer_script(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AnswerScriptRead:
    service = AnswerScriptService(db)
    entity = await service.request_cancel(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_SCRIPTS_DELETE))],
)
async def delete_answer_script(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> None:
    service = AnswerScriptService(db)
    await service.soft_delete(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ANSWER_SCRIPT_DELETED,
    )
    await db.commit()


@router.post(
    "/{entity_id}/restore",
    response_model=AnswerScriptRead,
    dependencies=[Depends(require_permissions(PermissionCode.ANSWER_SCRIPTS_DELETE))],
)
async def restore_answer_script(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AnswerScriptRead:
    service = AnswerScriptService(db)
    entity = await service.restore(
        institution_id,
        entity_id,
        actor_id=current_user.id,
        action=AuditAction.ACADEMIC_ENTITY_RESTORED,
    )
    await db.commit()
    return _to_read(entity)
