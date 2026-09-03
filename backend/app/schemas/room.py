"""Room schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema

RoomType = Literal["classroom", "lab", "auditorium", "seminar_hall", "other"]


class RoomRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    campus_id: uuid.UUID
    name: str
    building: str | None = None
    floor: str | None = None
    capacity: int
    room_type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RoomCreate(BaseSchema):
    campus_id: uuid.UUID
    name: str = Field(min_length=1, max_length=50)
    building: str | None = Field(default=None, max_length=100)
    floor: str | None = Field(default=None, max_length=20)
    capacity: int = Field(ge=1)
    room_type: RoomType


class RoomUpdate(BaseSchema):
    campus_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=50)
    building: str | None = Field(default=None, max_length=100)
    floor: str | None = Field(default=None, max_length=20)
    capacity: int | None = Field(default=None, ge=1)
    room_type: RoomType | None = None
    is_active: bool | None = None
