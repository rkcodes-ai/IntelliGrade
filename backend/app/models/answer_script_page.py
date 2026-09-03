"""AnswerScriptPage — one physical page of an AnswerScript, after page-splitting (Module 05)."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AnswerScriptPage(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One physical page belonging to an `AnswerScript`, one row per page
    after Stage 4/6's page-splitting (a multi-page PDF or a double-page
    scan both fan out into one `AnswerScriptPage` row each). `status`
    tracks this page's own pipeline progress independently of its parent
    `AnswerScript.status` — a script can be "preprocessing" while some
    pages are already "preprocessed" and others are still "pending".

    `answer_script_id` is a raw FK column only, `ondelete="CASCADE"`
    (deleting the script deletes its pages). `(answer_script_id,
    page_number)` is unique — the same page number can't be recorded
    twice for one script.
    """

    __tablename__ = "answer_script_pages"
    __table_args__ = (
        UniqueConstraint("answer_script_id", "page_number", name="uq_answer_script_page_number"),
    )

    answer_script_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("answer_scripts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preprocessed_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_blank: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)

    # Document Intelligence milestone (additive) — `PageQualityAnalyzer`/
    # `AdaptiveImageEnhancer` output. `quality_metrics`/`enhancement_metadata`
    # each hold one structured JSON blob (see
    # `app.services.document_intelligence.quality.PageQualityReport
    # .to_metrics_dict()`), the same "one JSON column, not eight" convention
    # already used elsewhere (e.g. `OCRProviderCandidate.structured_content`).
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    quality_classification: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quality_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    enhancement_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    processing_substage: Mapped[str | None] = mapped_column(String(30), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AnswerScriptPage id={self.id} page_number={self.page_number}>"
