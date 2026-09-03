"""Session schemas."""

import uuid
from datetime import datetime

from app.schemas.base import BaseSchema


class SessionRead(BaseSchema):
    id: uuid.UUID
    ip_address: str | None = None
    user_agent: str | None = None
    device_label: str | None = None
    is_active: bool
    last_active_at: datetime
    expires_at: datetime
    created_at: datetime
    is_current: bool = False
