"""NotificationEvent — storage-only notification framework (Module 07). See ADR-046.

No delivery channel exists yet (no email/SMS/push) — this table exists so
that services which already perform a notification-worthy action (result
published, evaluation ready for review, ...) can record the event now,
ready for a future delivery consumer to read from later.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class NotificationEvent(
    UUIDPrimaryKeyMixin, InstitutionOwnedMixin, TimestampMixin, SoftDeleteMixin, Base
):
    """
    One notification event for one recipient user.

    `event_type` is a free-form string (e.g. `"result_published"`,
    `"evaluation_ready_for_review"`) rather than a DB enum — new event
    types are added by services over time without a migration, same
    idiom as `AnswerScript.status`/`ExamSession.status`. `payload` carries
    whatever context a future delivery channel or the frontend bell-icon
    list needs (exam name, subject, marks, ...).
    """

    __tablename__ = "notification_events"

    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<NotificationEvent id={self.id} event_type={self.event_type!r}>"
