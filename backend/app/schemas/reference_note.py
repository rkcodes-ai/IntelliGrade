"""ReferenceNote schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema

#: `"ai_note"` is a category placeholder per ADR-024 for future AI-generated
#: notes — no code writes one yet.
NoteType = Literal["teacher_note", "ai_note"]


class ReferenceNoteRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    answer_key_id: uuid.UUID
    note_text: str
    note_type: NoteType
    created_at: datetime
    updated_at: datetime


class ReferenceNoteCreate(BaseSchema):
    answer_key_id: uuid.UUID
    note_text: str = Field(min_length=1)
    note_type: NoteType = "teacher_note"


class ReferenceNoteUpdate(BaseSchema):
    """Deliberately excludes `answer_key_id` — the parent link is fixed at creation."""

    note_text: str | None = Field(default=None, min_length=1)
    note_type: NoteType | None = None
