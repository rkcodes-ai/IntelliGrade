"""QuestionReview schemas — informal peer feedback on a `Question`."""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class QuestionReviewRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    question_id: uuid.UUID
    reviewer_id: uuid.UUID | None = None
    comment: str
    rating: int | None = None
    created_at: datetime
    updated_at: datetime


class QuestionReviewCreate(BaseSchema):
    """`reviewer_id` is deliberately absent: the router sets it from `current_user.id`."""

    question_id: uuid.UUID
    comment: str = Field(min_length=1)
    rating: int | None = Field(default=None, ge=1, le=5)


class QuestionReviewUpdate(BaseSchema):
    comment: str | None = Field(default=None, min_length=1)
    rating: int | None = Field(default=None, ge=1, le=5)
