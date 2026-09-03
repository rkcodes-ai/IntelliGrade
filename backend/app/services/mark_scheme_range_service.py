"""
MarkSchemeRange management service.

Rows are written internally by the ingestion pipeline
(`app.tasks.official_document_tasks`), never via a client-facing `POST` —
this service only supports reading, teacher-editing the range bounds via
`update()`, marking a range verified via `verify()`, and read-only
expansion of a document's full mark scheme into a per-question maximum-
marks map via `expand_for_document()`.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.models.mark_scheme_range import MarkSchemeRange
from app.repositories.mark_scheme_range_repository import MarkSchemeRangeRepository
from app.schemas.mark_scheme_range import MarkSchemeRangeUpdate
from app.services.audit_service import AuditService
from app.services.mark_scheme_service import MarkSchemeExpansionResult
from app.services.tenant_service import TenantScopedService


class MarkSchemeRangeService(TenantScopedService[MarkSchemeRange]):
    resource_type = "mark_scheme_range"

    def __init__(
        self,
        session: AsyncSession,
        repo: MarkSchemeRangeRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or MarkSchemeRangeRepository(session), audit_service=audit_service
        )

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: MarkSchemeRangeUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> MarkSchemeRange:
        entity = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(entity, field, value)
        entity.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(entity)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, entity.id)
        return entity

    async def verify(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> MarkSchemeRange:
        entity = await self.get_by_id(institution_id, entity_id)
        entity.verification_status = "verified"
        entity.verified_by = actor_id
        entity.verified_at = datetime.now(UTC)
        entity.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(entity)
        await self._log_audit(AuditAction.MARK_SCHEME_RANGE_VERIFIED, actor_id, entity.id)
        return entity

    async def expand_for_document(
        self, institution_id: uuid.UUID, document_id: uuid.UUID
    ) -> MarkSchemeExpansionResult:
        """Loads every MarkSchemeRange for this document and expands them via
        app.services.mark_scheme_service.expand_mark_scheme_ranges. Read-only —
        does not write final_marks onto any ExtractedQuestion row (that's a
        separate, explicit teacher action once ranges are verified, not
        implemented in this task)."""
        from sqlalchemy import select

        from app.services.mark_scheme_service import expand_mark_scheme_ranges

        query = select(MarkSchemeRange).where(
            MarkSchemeRange.institution_id == institution_id,
            MarkSchemeRange.document_id == document_id,
            MarkSchemeRange.deleted_at.is_(None),
        )
        ranges = list((await self.session.execute(query)).scalars().all())
        return expand_mark_scheme_ranges(ranges)
