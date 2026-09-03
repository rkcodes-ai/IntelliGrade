"""Institution schemas."""

import uuid
from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.base import BaseSchema


class InstitutionRead(BaseSchema):
    id: uuid.UUID
    name: str
    code: str
    institution_type: str
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    website: str | None = None
    established_year: int | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class InstitutionCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    institution_type: str = Field(max_length=32)
    address: str | None = None
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    website: str | None = Field(default=None, max_length=500)
    established_year: int | None = Field(default=None, ge=1000, le=2200)


class InstitutionUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    institution_type: str | None = Field(default=None, max_length=32)
    address: str | None = None
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    website: str | None = Field(default=None, max_length=500)
    established_year: int | None = Field(default=None, ge=1000, le=2200)
    is_active: bool | None = None


class UserInstitutionRead(BaseSchema):
    id: uuid.UUID
    user_id: uuid.UUID
    institution_id: uuid.UUID
    is_primary: bool
    is_active: bool
    joined_at: datetime


class UserInstitutionAssign(BaseSchema):
    user_id: uuid.UUID
    is_primary: bool = False
