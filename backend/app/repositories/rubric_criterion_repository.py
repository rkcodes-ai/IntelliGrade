"""Persistence access for `RubricCriterion`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rubric_criterion import RubricCriterion
from app.repositories.tenant_repository import TenantScopedRepository


class RubricCriterionRepository(TenantScopedRepository[RubricCriterion]):
    search_fields = ("name",)
    sortable_fields = ("name", "max_marks", "display_order", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RubricCriterion, session)
