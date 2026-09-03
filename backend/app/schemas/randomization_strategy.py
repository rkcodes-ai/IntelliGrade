"""RandomizationStrategy schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from app.schemas.base import BaseSchema

StrategyType = Literal["none", "shuffle_questions", "shuffle_options", "pick_random_subset"]


class RandomizationStrategyRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    question_paper_id: uuid.UUID | None = None
    question_paper_section_id: uuid.UUID | None = None
    strategy_type: StrategyType
    config: dict[str, Any] | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RandomizationStrategyCreate(BaseSchema):
    question_paper_id: uuid.UUID | None = None
    question_paper_section_id: uuid.UUID | None = None
    strategy_type: StrategyType = "none"
    config: dict[str, Any] | None = None


class RandomizationStrategyUpdate(BaseSchema):
    question_paper_id: uuid.UUID | None = None
    question_paper_section_id: uuid.UUID | None = None
    strategy_type: StrategyType | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None
