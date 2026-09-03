"""OfficialExamDocumentPage schemas — read-only, see the endpoint module."""

import uuid
from datetime import datetime

from app.schemas.base import BaseSchema


class OfficialExamDocumentPageRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    document_id: uuid.UUID
    page_number: int
    storage_key: str | None = None
    width_px: int | None = None
    height_px: int | None = None
    is_blank: bool
    status: str
    created_at: datetime
    updated_at: datetime
