"""User identity + profile schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import EmailStr, Field, field_validator

from app.core.password_policy import validate_password_field
from app.schemas.base import BaseSchema


class UserRead(BaseSchema):
    """Full user representation — used by `/users/me` and admin user endpoints."""

    id: uuid.UUID
    email: EmailStr
    username: str
    full_name: str
    phone: str | None = None
    avatar_url: str | None = None
    timezone: str
    language: str
    preferences: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    is_verified: bool
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(
        default_factory=list,
        description="Effective permission codes from all assigned roles — "
        "powers frontend permission guards without a second round-trip.",
    )
    last_login_at: datetime | None = None
    created_at: datetime


class UserPublic(BaseSchema):
    """Minimal, safe-to-embed user reference (e.g. `created_by` on other resources)."""

    id: uuid.UUID
    username: str
    full_name: str


class UserCreate(BaseSchema):
    """Admin-initiated user creation (`POST /users`)."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    timezone: str = Field(default="UTC", max_length=64)
    language: str = Field(default="en", max_length=10)
    role_names: list[str] = Field(default_factory=list)

    _validate_password = field_validator("password")(validate_password_field)


class UserUpdate(BaseSchema):
    """Admin-initiated update of another user (`PATCH /users/{id}`)."""

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=64)
    language: str | None = Field(default=None, max_length=10)


class UserProfileUpdate(BaseSchema):
    """Self-service profile update (`PATCH /users/me`) — no admin-only fields."""

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    avatar_url: str | None = Field(default=None, max_length=500)
    timezone: str | None = Field(default=None, max_length=64)
    language: str | None = Field(default=None, max_length=10)
    preferences: dict[str, Any] | None = None
