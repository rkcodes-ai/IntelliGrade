"""
OfficialExamDocument upload orchestration service (Module 06). Mirrors
`app.services.answer_script_service.AnswerScriptService` closely — same
validate/scan/checksum/duplicate-check/store shape — but the parent is
`exam_id` (exam-level), not `exam_session_id` (per-student), and there is
no `UploadJob` side-table (Module 06 has no chunked-upload story to track
yet; a single-request upload is recorded entirely on the document row
itself).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.official_exam_document import OfficialExamDocument
from app.repositories.official_exam_document_repository import OfficialExamDocumentRepository
from app.services.answer_script_service import scan_for_viruses_placeholder
from app.services.audit_service import AuditService
from app.services.official_document_storage_keys import build_official_document_key
from app.services.storage_service import StorageService, compute_sha256
from app.services.tenant_service import TenantScopedService

settings = get_settings()

_VALID_DOCUMENT_TYPES = ("question_paper", "model_answer", "mark_scheme")


class OfficialExamDocumentService(TenantScopedService[OfficialExamDocument]):
    resource_type = "official_exam_document"

    def __init__(
        self,
        session: AsyncSession,
        repo: OfficialExamDocumentRepository | None = None,
        storage: StorageService | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        repo = repo or OfficialExamDocumentRepository(session)
        super().__init__(session, repo, audit_service=audit_service)
        self._document_repo = repo
        self._storage = storage or StorageService()

    def validate_candidate(
        self, *, document_type: str, mime_type: str, file_size_bytes: int
    ) -> None:
        if document_type not in _VALID_DOCUMENT_TYPES:
            raise ValidationAppError(
                f"Unsupported document_type '{document_type}'. "
                f"Allowed: {', '.join(_VALID_DOCUMENT_TYPES)}."
            )
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
        # Reused, read-only, from Module 05 — not duplicated (see
        # docs/storage-guide.md).
        scan_for_viruses_placeholder(file_bytes)

    async def upload(
        self,
        institution_id: uuid.UUID,
        *,
        exam_id: uuid.UUID,
        document_type: str,
        original_filename: str,
        mime_type: str,
        file_bytes: bytes,
        uploaded_by: uuid.UUID | None,
        allow_duplicate: bool = False,
    ) -> OfficialExamDocument:
        # Local import: `ExamRepository` (Module 04) — matches the
        # established cross-entity-validation idiom in this module family,
        # not an import-order hazard.
        from app.repositories.exam_repository import ExamRepository

        exam = await ExamRepository(self.session).get_by_id_for_institution(exam_id, institution_id)
        if exam is None:
            raise NotFoundError("Exam not found.")

        self.validate_candidate(
            document_type=document_type, mime_type=mime_type, file_size_bytes=len(file_bytes)
        )
        self.scan_candidate(file_bytes)
        checksum = compute_sha256(file_bytes)

        if not allow_duplicate:
            duplicate = await self._document_repo.find_duplicate(
                institution_id, exam_id, document_type, checksum
            )
            if duplicate is not None:
                raise ConflictError(
                    "An identical file has already been uploaded for this exam/document type.",
                    details={"existing_document_id": str(duplicate.id)},
                )

        document = OfficialExamDocument(
            institution_id=institution_id,
            exam_id=exam_id,
            uploaded_by=uploaded_by,
            document_type=document_type,
            original_filename=original_filename,
            mime_type=mime_type,
            file_size_bytes=len(file_bytes),
            checksum_sha256=checksum,
            ocr_status="uploaded",
            verification_status="not_started",
            is_active=True,
            created_by=uploaded_by,
        )
        document = await self._document_repo.add(document)

        storage_key = build_official_document_key(institution_id, document.id, original_filename)
        document.ocr_status = "storing"
        await self.session.flush()
        meta = await self._storage.put_bytes(storage_key, file_bytes, mime_type)
        document.storage_key = meta.key
        document.ocr_status = "stored"
        await self.session.flush()
        await self.session.refresh(document)

        await self._log_audit(AuditAction.OFFICIAL_EXAM_DOCUMENT_UPLOADED, uploaded_by, document.id)
        return document

    async def request_retry(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> OfficialExamDocument:
        document = await self.get_by_id(institution_id, entity_id)
        if document.ocr_status not in ("failed", "cancelled"):
            raise ConflictError(
                f"Cannot retry a document in status '{document.ocr_status}'. "
                "Retry is only valid after a failure or cancellation."
            )
        document.ocr_status = "stored"
        document.failure_reason = None
        document.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(document)
        await self._log_audit(
            AuditAction.OFFICIAL_EXAM_DOCUMENT_RETRY_REQUESTED, actor_id, document.id
        )
        return document

    async def request_cancel(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> OfficialExamDocument:
        document = await self.get_by_id(institution_id, entity_id)
        if document.ocr_status in ("completed", "failed", "cancelled"):
            raise ConflictError(
                f"Cannot cancel a document already in status '{document.ocr_status}'."
            )
        document.ocr_status = "cancelled"
        document.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(document)
        await self._log_audit(AuditAction.OFFICIAL_EXAM_DOCUMENT_CANCELLED, actor_id, document.id)
        return document

    async def mark_failed(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        *,
        reason: str,
        actor_id: uuid.UUID | None,
    ) -> OfficialExamDocument:
        document = await self.get_by_id(institution_id, entity_id)
        document.ocr_status = "failed"
        document.failure_reason = reason
        document.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(document)
        return document
