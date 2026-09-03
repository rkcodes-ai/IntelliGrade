"""Persistence access for `ExpectedKeyword`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expected_keyword import ExpectedKeyword
from app.repositories.tenant_repository import TenantScopedRepository


class ExpectedKeywordRepository(TenantScopedRepository[ExpectedKeyword]):
    search_fields = ("keyword",)
    sortable_fields = ("keyword", "weight", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ExpectedKeyword, session)
