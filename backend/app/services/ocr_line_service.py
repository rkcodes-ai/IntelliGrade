"""OCRLineService — read-only access to `OCRLine` rows."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ocr_line import OCRLine
from app.repositories.ocr_line_repository import OCRLineRepository
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class OCRLineService(TenantScopedService[OCRLine]):
    """
    Entirely read-only from the API's perspective -- `OCRLine` rows are
    written only by `OCRResultService.create_with_hierarchy()`, never
    individually, so this service has no standalone `create()`. Exists for
    its `GET` endpoints' `list_paginated`/`get_by_id` needs (inherited
    unchanged from `TenantScopedService`).
    """

    resource_type = "ocr_line"

    def __init__(
        self,
        session: AsyncSession,
        repo: OCRLineRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session, repo or OCRLineRepository(session), audit_service=audit_service)
