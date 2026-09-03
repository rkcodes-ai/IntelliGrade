"""Persistence access for `OfficialExamDocumentPage`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.official_exam_document_page import OfficialExamDocumentPage
from app.repositories.tenant_repository import TenantScopedRepository


class OfficialExamDocumentPageRepository(TenantScopedRepository[OfficialExamDocumentPage]):
    sortable_fields = ("page_number", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(OfficialExamDocumentPage, session)
