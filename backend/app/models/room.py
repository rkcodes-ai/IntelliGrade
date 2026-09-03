"""Room — a physical room on a Campus (Module 03 Academic Domain)."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Room(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A room belongs to exactly one campus; name is unique per campus.
    `campus_id` is a raw FK column only (no `relationship()`) — `Campus` is
    owned by a sibling agent's model file, see `app/models/campus.py`.
    `room_type` is a free-form string validated at the schema layer
    (`Literal["classroom", "lab", "auditorium", "seminar_hall", "other"]`),
    not constrained in the database — see `app/schemas/room.py`.
    """

    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("campus_id", "name", name="uq_room_campus_name"),)

    campus_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("campuses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    building: Mapped[str | None] = mapped_column(String(100), nullable=True)
    floor: Mapped[str | None] = mapped_column(String(20), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    room_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Room id={self.id} name={self.name!r}>"
