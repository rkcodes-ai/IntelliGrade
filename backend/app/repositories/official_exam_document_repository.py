"""Persistence access for `OfficialExamDocument`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.official_exam_document import OfficialExamDocument
from app.repositories.tenant_repository import TenantScopedRepository


class OfficialExamDocumentRepository(TenantScopedRepository[OfficialExamDocument]):
    search_fields = ("original_filename",)
    sortable_fields = ("created_at", "updated_at", "document_type", "ocr_status")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(OfficialExamDocument, session)

    async def find_duplicate(
        self,
        institution_id: uuid.UUID,
        exam_id: uuid.UUID,
        document_type: str,
        checksum_sha256: str,
    ) -> OfficialExamDocument | None:
        query = select(OfficialExamDocument).where(
            OfficialExamDocument.institution_id == institution_id,
            OfficialExamDocument.exam_id == exam_id,
            OfficialExamDocument.document_type == document_type,
            OfficialExamDocument.checksum_sha256 == checksum_sha256,
            OfficialExamDocument.deleted_at.is_(None),
        )
        result = await self.session.execute(query)
        return result.scalars().first()
