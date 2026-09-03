"""Institution — the tenant root. Every other academic table belongs to one."""

from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user_institution import UserInstitution


class InstitutionType(StrEnum):
    UNIVERSITY = "university"
    COLLEGE = "college"
    SCHOOL = "school"
    INSTITUTE = "institute"


class Institution(UUIDPrimaryKeyMixin, TimestampMixin, AuditActorMixin, SoftDeleteMixin, Base):
    """
    The tenant root of the Academic Domain (Module 03). Has no
    `institution_id` of its own — every other academic table has a
    mandatory FK to this table (see `app.models.academic_base.InstitutionOwnedMixin`
    and ADR-016 in `ARCHITECTURE_DECISIONS.md`).

    Deliberately has no FK to `users.id` for its "owner" — membership is
    modeled separately via `UserInstitution` (a user may belong to more
    than one institution) so this table never needs to change if the
    membership model evolves. See ADR-014.
    """

    __tablename__ = "institutions"

    name: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    institution_type: Mapped[str] = mapped_column(String(32), nullable=False)

    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    established_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user_memberships: Mapped[list["UserInstitution"]] = relationship(
        back_populates="institution", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Institution id={self.id} code={self.code!r}>"
