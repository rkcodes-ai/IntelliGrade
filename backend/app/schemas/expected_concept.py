"""ExpectedConcept schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class ExpectedConceptRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    answer_key_id: uuid.UUID | None = None
    rubric_criterion_id: uuid.UUID | None = None
    concept_name: str
    description: str | None = None
    is_mandatory: bool
    created_at: datetime
    updated_at: datetime


class ExpectedConceptCreate(BaseSchema):
    answer_key_id: uuid.UUID | None = None
    rubric_criterion_id: uuid.UUID | None = None
    concept_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    is_mandatory: bool = False


class ExpectedConceptUpdate(BaseSchema):
    answer_key_id: uuid.UUID | None = None
    rubric_criterion_id: uuid.UUID | None = None
    concept_name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    is_mandatory: bool | None = None
