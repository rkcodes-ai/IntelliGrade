"""OfficialExamDocumentPage — one physical page of an OfficialExamDocument,
written internally by the Module 06 ingestion pipeline (Module 06)."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class OfficialExamDocumentPage(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One page of an `OfficialExamDocument`'s preprocessed image, mirroring
    `AnswerScriptPage`'s shape (Module 05) — kept as a genuinely new,
    parallel table rather than reusing `AnswerScriptPage` itself, since
    that table's parent FK is `answer_script_id` (per ADR-035/ADR-036, no
    Module 05 table or FK is touched).

    Not exposed via any client-facing create route — pages are written
    internally by `app/tasks/official_document_tasks.py` during page
    extraction/preprocessing, the same "pipeline-only" convention as
    `AnswerScriptPage`.
    """

    __tablename__ = "official_exam_document_pages"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("official_exam_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Document Intelligence milestone (additive) — mirrors `AnswerScriptPage`'s
    # already-existing `preprocessed_storage_key`/quality/enhancement fields,
    # which this parallel Module 06 table never had until now.
    preprocessed_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_blank: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    quality_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    quality_classification: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quality_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    enhancement_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    processing_substage: Mapped[str | None] = mapped_column(String(30), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<OfficialExamDocumentPage id={self.id} document_id={self.document_id} "
            f"page_number={self.page_number}>"
        )
