"""Persistence access for `SubjectAllocation`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subject_allocation import SubjectAllocation
from app.repositories.tenant_repository import TenantScopedRepository


class SubjectAllocationRepository(TenantScopedRepository[SubjectAllocation]):
    #: No text search — this is a join/link entity between Subject/Section/
    #: Semester with no free-text field of its own; list by filters instead.
    search_fields: tuple[str, ...] = ()
    sortable_fields = ("created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SubjectAllocation, session)
