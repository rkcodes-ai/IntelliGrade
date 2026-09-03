"""Subject — an individual academic paper taught within a Course (Module 03 Academic Domain)."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Subject(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A subject (e.g. "Data Structures") belongs to exactly one course and is
    categorized by a `SubjectCategory`; `code` is unique per institution.
    `course_id` and `subject_category_id` are raw FK columns only (no
    `relationship()`) — `Course` and `SubjectCategory` were both built in
    Wave 1, see `app/models/course.py` and `app/models/subject_category.py`.
    `subject_category_id` uses `ondelete="RESTRICT"` (unlike most Module 03
    parent FKs, which cascade) so a category in active use by a subject
    cannot be deleted out from under it — see `app/services/subject_service.py`.
    """

    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_subject_institution_code"),
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subject_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    credits: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    semester_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Subject id={self.id} code={self.code!r}>"
