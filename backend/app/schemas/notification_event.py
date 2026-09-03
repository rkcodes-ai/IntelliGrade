"""NotificationEvent schemas (Module 07). See ADR-046.

No client-facing `Create`: notification events are written internally by
whichever service just performed a notification-worthy action (e.g.
`ExamResultService.publish()`), never accepted as an arbitrary
client-supplied payload.
"""

import uuid
from datetime import datetime
from typing import Any

from app.schemas.base import BaseSchema


class NotificationEventRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    recipient_user_id: uuid.UUID
    event_type: str
    payload: dict[str, Any] | None = None
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
