"""AnswerScriptPage schemas — read-only from the API's perspective; rows are pipeline-managed."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from app.schemas.base import BaseSchema

AnswerScriptPageStatus = Literal[
    "pending", "preprocessing", "preprocessed", "ocr_running", "ocr_complete", "ocr_failed"
]


class AnswerScriptPageRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    answer_script_id: uuid.UUID
    page_number: int
    storage_key: str | None = None
    preprocessed_storage_key: str | None = None
    width_px: int | None = None
    height_px: int | None = None
    is_blank: bool
    status: AnswerScriptPageStatus
    # Document Intelligence milestone (additive) — PageQualityAnalyzer/
    # AdaptiveImageEnhancer output, `None` for any page processed before
    # this milestone (or when quality analysis/enhancement failed and
    # safely fell back to the original image).
    quality_score: Decimal | None = None
    quality_classification: str | None = None
    quality_metrics: dict[str, Any] | None = None
    enhancement_metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
