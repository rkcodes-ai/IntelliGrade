"""Persistence access for `ReferenceNote`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reference_note import ReferenceNote
from app.repositories.tenant_repository import TenantScopedRepository


class ReferenceNoteRepository(TenantScopedRepository[ReferenceNote]):
    search_fields: tuple[str, ...] = ("note_text",)
    sortable_fields = ("created_at", "updated_at", "note_type")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ReferenceNote, session)
