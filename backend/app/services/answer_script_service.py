"""
AnswerScript upload orchestration service.

`upload()` is the single-shot (non-chunked) path — the realistic common
case for most answer-script files. It validates the candidate file
(format/size/duplicate), persists the `AnswerScript` + a completed
`UploadJob` row, writes the original bytes to permanent object storage,
and leaves the script in `"stored"` status ready for the pipeline (Stage
4 onward) to pick up — this service does NOT itself trigger OCR; that's
`app.tasks.ocr_tasks`'s job, kicked off by the endpoint after this method
returns (keeping "persist the upload" and "run the pipeline" as two
separately-testable concerns).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.answer_script import AnswerScript
from app.models.upload_job import UploadJob
from app.repositories.answer_script_repository import AnswerScriptRepository
from app.repositories.upload_job_repository import UploadJobRepository
from app.services.audit_service import AuditService
from app.services.storage_service import StorageService, build_original_key, compute_sha256
from app.services.tenant_service import TenantScopedService

settings = get_settings()


def scan_for_viruses_placeholder(file_bytes: bytes) -> None:
    """Virus/malware scan extension point — no scanning engine is wired in
    yet (see `docs/storage-guide.md`). Deliberately a no-op today rather
    than absent entirely: a future integration (e.g. ClamAV) replaces this
    function's body without touching any caller. Every uploaded file
    passes through here so that wiring stays a one-function change."""
    return None


class AnswerScriptService(TenantScopedService[AnswerScript]):
    resource_type = "answer_script"

    def __init__(
        self,
        session: AsyncSession,
        repo: AnswerScriptRepository | None = None,
        upload_job_repo: UploadJobRepository | None = None,
        storage: StorageService | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        repo = repo or AnswerScriptRepository(session)
        super().__init__(session, repo, audit_service=audit_service)
        self._answer_script_repo = repo
        self._upload_job_repo = upload_job_repo or UploadJobRepository(session)
        self._storage = storage or StorageService()

    def validate_candidate(self, *, mime_type: str, file_size_bytes: int) -> None:
        if mime_type not in settings.UPLOAD_ALLOWED_MIME_TYPES:
            raise ValidationAppError(
                f"Unsupported file type '{mime_type}'. "
                f"Allowed: {', '.join(settings.UPLOAD_ALLOWED_MIME_TYPES)}."
            )
        if file_size_bytes <= 0:
            raise ValidationAppError("Uploaded file is empty.")
        if file_size_bytes > settings.UPLOAD_MAX_FILE_SIZE_BYTES:
            max_mb = settings.UPLOAD_MAX_FILE_SIZE_BYTES / (1024 * 1024)
            raise ValidationAppError(f"File exceeds the maximum allowed size of {max_mb:.0f} MB.")

    def scan_candidate(self, file_bytes: bytes) -> None:
        scan_for_viruses_placeholder(file_bytes)

    async def upload(
        self,
        institution_id: uuid.UUID,
        *,
        exam_session_id: uuid.UUID,
        original_filename: str,
        mime_type: str,
        file_bytes: bytes,
        uploaded_by: uuid.UUID | None,
        allow_duplicate: bool = False,
    ) -> AnswerScript:
        # Local import: `ExamSessionRepository` (Module 04) is a stable,
        # already-existing model — imported locally only to match this
        # module's established cross-entity-validation idiom, not because
        # of an import-order hazard here.
        from app.repositories.exam_session_repository import ExamSessionRepository

        exam_session = await ExamSessionRepository(self.session).get_by_id_for_institution(
            exam_session_id, institution_id
        )
        if exam_session is None:
            raise NotFoundError("Exam session not found.")

        self.validate_candidate(mime_type=mime_type, file_size_bytes=len(file_bytes))
        self.scan_candidate(file_bytes)
        checksum = compute_sha256(file_bytes)

        if not allow_duplicate:
            duplicate = await self._answer_script_repo.find_duplicate(
                institution_id, exam_session_id, checksum
            )
            if duplicate is not None:
                raise ConflictError(
                    "An identical file has already been uploaded for this exam session.",
                    details={"existing_answer_script_id": str(duplicate.id)},
                )

        script = AnswerScript(
            institution_id=institution_id,
            exam_session_id=exam_session_id,
            uploaded_by=uploaded_by,
            original_filename=original_filename,
            mime_type=mime_type,
            file_size_bytes=len(file_bytes),
            checksum_sha256=checksum,
            status="uploaded",
            is_active=True,
            created_by=uploaded_by,
        )
        script = await self._answer_script_repo.add(script)

        storage_key = build_original_key(institution_id, script.id, original_filename)
        script.status = "storing"
        await self.session.flush()
        meta = await self._storage.put_bytes(storage_key, file_bytes, mime_type)
        script.storage_key = meta.key
        script.status = "stored"
        await self.session.flush()
        await self.session.refresh(script)

        upload_job = UploadJob(
            institution_id=institution_id,
            answer_script_id=script.id,
            upload_session_token=str(uuid.uuid4()),
            total_chunks=1,
            chunks_received=1,
            bytes_received=len(file_bytes),
            total_bytes=len(file_bytes),
            status="completed",
            created_by=uploaded_by,
        )
        await self._upload_job_repo.add(upload_job)

        await self._log_audit(AuditAction.ANSWER_SCRIPT_UPLOADED, uploaded_by, script.id)
        return script

    async def request_retry(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> AnswerScript:
        script = await self.get_by_id(institution_id, entity_id)
        if script.status not in ("failed", "failed_validation", "ocr_failed", "cancelled"):
            raise ConflictError(
                f"Cannot retry an answer script in status '{script.status}'. "
                "Retry is only valid after a failure or cancellation."
            )
        script.status = "ocr_queued"
        script.failure_reason = None
        script.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(script)
        await self._log_audit(AuditAction.ANSWER_SCRIPT_RETRY_REQUESTED, actor_id, script.id)
        return script

    async def request_cancel(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> AnswerScript:
        script = await self.get_by_id(institution_id, entity_id)
        if script.status in ("completed", "failed", "cancelled"):
            raise ConflictError(
                f"Cannot cancel an answer script already in status '{script.status}'."
            )
        script.status = "cancelled"
        script.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(script)
        await self._log_audit(AuditAction.OCR_JOB_CANCELLED, actor_id, script.id)
        return script

    async def mark_failed(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        *,
        reason: str,
        actor_id: uuid.UUID | None,
    ) -> AnswerScript:
        script = await self.get_by_id(institution_id, entity_id)
        script.status = "failed"
        script.failure_reason = reason
        script.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(script)
        await self._log_audit(AuditAction.OCR_PROCESSING_FAILED, actor_id, script.id)
        return script
