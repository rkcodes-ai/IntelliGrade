"""Persistence access for `Section`."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.section import Section
from app.repositories.tenant_repository import TenantScopedRepository


class SectionRepository(TenantScopedRepository[Section]):
    search_fields = ("name",)
    sortable_fields = ("name", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Section, session)

    async def count_active_enrollments(self, section_id: uuid.UUID) -> int:
        """
        Number of active student enrollments in this section.

        # TODO(Module 03 integration): wire to student_enrollments once
        # that table exists — `StudentEnrollment` is being built by a
        # different parallel agent in this same wave and doesn't exist on
        # disk yet. A sibling entity will need this to enforce section
        # capacity when enrolling students; returning 0 for now keeps this
        # file importable without depending on a table that doesn't exist.
        """
        return 0
