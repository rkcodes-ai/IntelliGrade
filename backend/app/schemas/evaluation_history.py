"""EvaluationHistory schemas.

This entity is append-only in practice (see `app/models/evaluation_history.py`
and `app/api/v1/endpoints/evaluation_history.py`) — there is deliberately no
`EvaluationHistoryUpdate` schema, since no permission code
(`EVALUATION_HISTORY_UPDATE`) or route exists to use one.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field

from app.schemas.base import BaseSchema

EvaluatorType = Literal["human", "ai"]


class EvaluationHistoryRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    exam_session_id: uuid.UUID
    answer_key_id: uuid.UUID | None = None
    evaluator_type: EvaluatorType
    evaluator_user_id: uuid.UUID | None = None
    score: Decimal | None = None
    confidence_score: Decimal | None = None
    embedding_vector: list[Any] | None = None
    evaluated_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class EvaluationHistoryCreate(BaseSchema):
    exam_session_id: uuid.UUID
    answer_key_id: uuid.UUID | None = None
    evaluator_type: EvaluatorType = "human"
    evaluator_user_id: uuid.UUID | None = None
    score: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=2)
    confidence_score: Decimal | None = Field(
        default=None, ge=0, le=1, max_digits=4, decimal_places=3
    )
    embedding_vector: list[Any] | None = None
    evaluated_at: datetime | None = None
    notes: str | None = None
