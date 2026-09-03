"""Campus schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class CampusRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    name: str
    code: str
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    is_main_campus: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CampusCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    address: str | None = None
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    is_main_campus: bool = False


class CampusUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    address: str | None = None
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    is_main_campus: bool | None = None
    is_active: bool | None = None
