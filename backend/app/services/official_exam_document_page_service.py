"""
OfficialExamDocumentPage service. `create()` is not exposed via any
client-facing route — pages are written internally by
`app.tasks.official_document_tasks` during page extraction/preprocessing,
the same "pipeline-only" convention as Module 05's
`AnswerScriptPageService`.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.official_exam_document_page import OfficialExamDocumentPage
from app.repositories.official_exam_document_page_repository import (
    OfficialExamDocumentPageRepository,
)
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class OfficialExamDocumentPageService(TenantScopedService[OfficialExamDocumentPage]):
    resource_type = "official_exam_document_page"

    def __init__(
        self,
        session: AsyncSession,
        repo: OfficialExamDocumentPageRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session,
            repo or OfficialExamDocumentPageRepository(session),
            audit_service=audit_service,
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        page_number: int,
        storage_key: str | None = None,
        width_px: int | None = None,
        height_px: int | None = None,
        is_blank: bool = False,
        created_by: uuid.UUID | None = None,
    ) -> OfficialExamDocumentPage:
        page = OfficialExamDocumentPage(
            institution_id=institution_id,
            document_id=document_id,
            page_number=page_number,
            storage_key=storage_key,
            width_px=width_px,
            height_px=height_px,
            is_blank=is_blank,
            status="pending",
            created_by=created_by,
        )
        return await self.repo.add(page)
