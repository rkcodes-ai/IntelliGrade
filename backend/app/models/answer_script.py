"""AnswerScript — an uploaded, scanned answer booklet for one student's ExamSession (Module 05)."""

import uuid
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AnswerScript(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    Root entity of the OCR pipeline — one uploaded document (PDF or image)
    representing a student's physical answer booklet for one `ExamSession`.

    `DocumentMetadata` and `ProcessingStatus` (named as separate entities in
    the original brief) are consolidated into plain columns here rather
    than their own tables — see ADR-027. `status` is a plain string
    (`Literal[...]` at the Pydantic layer, no DB `CHECK`), covering the
    full pipeline state machine: uploading -> uploaded -> validating ->
    validated / failed_validation -> storing -> stored -> preprocessing ->
    ocr_queued -> ocr_running -> ocr_complete / ocr_failed -> structuring
    -> completed / failed / cancelled. `structured_content` is the Stage 8
    output (see ADR-031) — a nested JSON tree, schema documented in
    `docs/ocr-pipeline-guide.md`, not a relational Section/Heading/Table
    entity set.

    `exam_session_id` is a raw FK column only (no `relationship()`) into
    Module 04's `exam_sessions` table, `ondelete="CASCADE"` (a script is
    meaningless without the exam sitting it belongs to). `uploaded_by`
    points at `users.id` `ondelete="RESTRICT"` (typically a teacher/proctor
    scanning and uploading on a student's behalf, not the student).
    """

    __tablename__ = "answer_scripts"

    exam_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("exam_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="uploading", index=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_content: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AnswerScript id={self.id} status={self.status}>"
