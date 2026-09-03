"""OCRWordService — read-only access to `OCRWord` rows."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ocr_word import OCRWord
from app.repositories.ocr_word_repository import OCRWordRepository
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class OCRWordService(TenantScopedService[OCRWord]):
    """
    Entirely read-only from the API's perspective -- `OCRWord` rows are
    written only by `OCRResultService.create_with_hierarchy()`, never
    individually, so this service has no standalone `create()`. Exists for
    its `GET` endpoints' `list_paginated`/`get_by_id` needs (inherited
    unchanged from `TenantScopedService`).
    """

    resource_type = "ocr_word"

    def __init__(
        self,
        session: AsyncSession,
        repo: OCRWordRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session, repo or OCRWordRepository(session), audit_service=audit_service)
