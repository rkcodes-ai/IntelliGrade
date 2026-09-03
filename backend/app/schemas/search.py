"""Global Search schemas (Module 07, Feature 9)."""

import uuid
from typing import Literal

from app.schemas.base import BaseSchema

SearchResultType = Literal["student", "teacher", "subject", "question", "evaluation"]


class SearchResultItem(BaseSchema):
    type: SearchResultType
    id: uuid.UUID
    label: str
    subtitle: str | None = None


class SearchResults(BaseSchema):
    query: str
    results: list[SearchResultItem]
