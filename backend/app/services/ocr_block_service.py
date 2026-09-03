"""OCRBlockService — read-only access to `OCRBlock` rows."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ocr_block import OCRBlock
from app.repositories.ocr_block_repository import OCRBlockRepository
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class OCRBlockService(TenantScopedService[OCRBlock]):
    """
    Entirely read-only from the API's perspective -- `OCRBlock` rows are
    written only by `OCRResultService.create_with_hierarchy()`, never
    individually, so this service has no standalone `create()`. Exists for
    its `GET` endpoints' `list_paginated`/`get_by_id` needs (inherited
    unchanged from `TenantScopedService`).
    """

    resource_type = "ocr_block"

    def __init__(
        self,
        session: AsyncSession,
        repo: OCRBlockRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session, repo or OCRBlockRepository(session), audit_service=audit_service)
