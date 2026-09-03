"""BloomTaxonomyLevel — an institution-defined cognitive level for Questions
(Remember, Understand, Apply, Analyze, Evaluate, Create, ...).

Module 04 Assessment Domain.
"""

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class BloomTaxonomyLevel(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """A Bloom's taxonomy level; belongs to one institution, code unique per institution."""

    __tablename__ = "bloom_taxonomy_levels"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_bloom_taxonomy_level_institution_code"),
    )

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    #: Sort key for the taxonomy's natural cognitive-complexity order.
    level_order: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BloomTaxonomyLevel id={self.id} code={self.code!r}>"
