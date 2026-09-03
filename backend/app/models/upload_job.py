"""UploadJob — tracks one chunked/resumable upload attempt for an AnswerScript (Module 05)."""

import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class UploadJob(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One upload attempt against a parent `AnswerScript` — deliberately a
    separate entity from `AnswerScript` itself (see `docs/ocr-pipeline-
    guide.md`) so retrying a failed upload creates a NEW `UploadJob` row
    while the parent `AnswerScript` stays stable, giving "Retry support"
    a real audit trail instead of overwriting upload state in place.

    `upload_session_token` groups the chunks of one resumable upload
    attempt (client-generated or server-issued at `upload-init` time) —
    unique, so a client can safely resume by re-POSTing the same token
    without creating a duplicate job. `answer_script_id` is a raw FK
    column only, `ondelete="CASCADE"`.
    """

    __tablename__ = "upload_jobs"

    answer_script_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("answer_scripts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    upload_session_token: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    total_chunks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunks_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bytes_received: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UploadJob id={self.id} status={self.status}>"
