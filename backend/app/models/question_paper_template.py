"""QuestionPaperTemplate — a reusable header/footer/instructions layout for question papers.

Module 04 Assessment Domain.
"""

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class QuestionPaperTemplate(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    An independent, institution-scoped reusable layout (header/footer/
    instructions boilerplate) that a `QuestionPaper` can be generated from;
    `name` is unique per institution. Has no parent FK of its own — same
    "independent lookup" shape as `app/models/subject_category.py`.
    """

    __tablename__ = "question_paper_templates"
    __table_args__ = (
        UniqueConstraint(
            "institution_id", "name", name="uq_question_paper_template_institution_name"
        ),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    header_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    footer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<QuestionPaperTemplate id={self.id} name={self.name!r}>"
