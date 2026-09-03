"""Section — a fixed subdivision of a Batch, e.g. "CSE 2024 - Section A" (Module 03)."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Section(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A section belongs to exactly one batch; `name` is unique per batch.
    `batch_id` is a raw FK column only — `Batch` is defined in this same
    module (`app/models/batch.py`), built in this same task, so a
    `relationship()` would be safe, but a plain FK column keeps this model
    consistent with every other Module 03 entity (repositories filter/join
    by raw column, not ORM traversal).
    """

    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("batch_id", "name", name="uq_section_batch_name"),)

    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    max_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Section id={self.id} name={self.name!r}>"
