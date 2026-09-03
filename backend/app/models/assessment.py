"""Assessment — a gradable unit of work tied to a Subject (Module 04 Assessment Domain)."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.assessment_base import VersionCounterMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Assessment(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    VersionCounterMixin,
    Base,
):
    """
    An assessment (e.g. "Midterm Exam — Data Structures") belongs to exactly
    one `Subject` and is categorized by an `AssessmentType`, with a current
    `AssessmentStatus`. `subject_id` uses `ondelete="CASCADE"` (an assessment
    is meaningless without its subject), while `assessment_type_id` and
    `assessment_status_id` use `ondelete="RESTRICT"` (a lookup row still
    referenced by an assessment cannot be deleted out from under it) — same
    convention as `app/models/subject.py`'s `subject_category_id`. No unique
    constraint on `name`: multiple assessments per subject may legitimately
    share a name across different semesters/academic years. `current_version`
    (via `VersionCounterMixin`) is bumped by `AssessmentService.update` on any
    content-changing edit.
    """

    __tablename__ = "assessments"

    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assessment_status_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_statuses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Assessment id={self.id} name={self.name!r}>"
