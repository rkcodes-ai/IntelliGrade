"""OfficialExamDocument — root entity for Module 06 ingestion of
Exam-Cell-prepared official documents (Question Paper / Model Answer /
Mark Scheme PDFs). See ADR-035 in ARCHITECTURE_DECISIONS.md."""

import uuid
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class OfficialExamDocument(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One official PDF uploaded by the Exam Cell/Faculty for one `Exam` —
    a Question Paper, Model Answer, or Mark Scheme, distinguished by
    `document_type` (one table, not three near-identical ones, per
    ADR-035's consolidation precedent).

    `exam_id` is deliberately a raw FK to `exams.id` (Module 04),
    `ondelete="CASCADE"` — **exam-level, not session-level**: a Question
    Paper belongs to the exam as a whole, not to any one student's sitting
    of it, which is exactly why this cannot be `AnswerScript` (Module 05,
    hard-FK'd to `exam_sessions.id`). `uploaded_by` points at `users.id`,
    `ondelete="RESTRICT"`.

    `storage_key` (the original uploaded PDF) and `raw_ocr_text` (the
    whole-document OCR dump) are both **write-once** — set exactly once by
    the ingestion pipeline (`app/tasks/official_document_tasks.py`) and
    never modified afterward by any teacher-verification action. Per-item
    "Verified Output" lives on the child tables
    (`ExtractedQuestion`/`ExtractedModelAnswer`/`MarkSchemeRange`), not
    here — see ADR-035 for why a second JSON blob on this table would be
    redundant with those already-normalized child rows.

    `ocr_status` mirrors `AnswerScript.status`'s state-machine shape
    (its own value set, not shared) — `uploading` -> `uploaded` ->
    `validating` -> `validated`/`failed_validation` -> `storing` ->
    `stored` -> `preprocessing` -> `ocr_running` -> `ocr_complete`/
    `ocr_failed` -> `completed`/`failed`/`cancelled`. `verification_status`
    is a coarse rollup of the child rows' individual verification state
    (`not_started`/`in_progress`/`verified`), maintained by the service
    layer as children are verified — not itself the source of truth for
    any one item.
    """

    __tablename__ = "official_exam_documents"

    exam_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    document_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    raw_ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="uploading", index=True
    )
    verification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="not_started", index=True
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<OfficialExamDocument id={self.id} document_type={self.document_type!r} "
            f"ocr_status={self.ocr_status!r}>"
        )
