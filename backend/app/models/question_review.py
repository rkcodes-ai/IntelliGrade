"""QuestionReview — informal peer feedback on a `Question` (Module 04)."""

import uuid

from sqlalchemy import ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class QuestionReview(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    Informal peer feedback on a question (a free-text comment plus an
    optional 1-5 rating), distinct from `QuestionApproval`'s formal
    approve/reject decision record — a question can accumulate many reviews
    from different reviewers while only ever having one *active* approval
    decision per review cycle. Standard full CRUD, unlike its two siblings.
    """

    __tablename__ = "question_reviews"

    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<QuestionReview id={self.id} question_id={self.question_id}>"
