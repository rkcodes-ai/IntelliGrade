"""Role schemas."""

import uuid

from pydantic import Field

from app.schemas.base import BaseSchema


class RoleRead(BaseSchema):
    id: uuid.UUID
    name: str
    description: str | None = None
    is_system: bool
    permissions: list[str] = Field(default_factory=list)


class RoleAssignRequest(BaseSchema):
    """`POST /users/{id}/roles` — grant a role to a user."""

    role_name: str = Field(min_length=1, max_length=64)
