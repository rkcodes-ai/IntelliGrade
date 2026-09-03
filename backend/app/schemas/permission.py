"""Permission schemas."""

import uuid

from app.schemas.base import BaseSchema


class PermissionRead(BaseSchema):
    id: uuid.UUID
    code: str
    resource: str
    action: str
    description: str | None = None
