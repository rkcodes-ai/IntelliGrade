"""
DocumentRegion service (Document Intelligence milestone). `persist_regions()`
bulk-writes one `DetectedRegion` (in-memory dataclass from
`app.services.document_intelligence.layout`) per row, same
`session.add_all()` + flush pattern `OCRResultService.persist_candidates()`
already uses for `OCRProviderCandidate` — caller commits afterward.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_region import DocumentRegion
from app.repositories.document_region_repository import DocumentRegionRepository
from app.services.audit_service import AuditService
from app.services.document_intelligence.layout import DetectedRegion
from app.services.tenant_service import TenantScopedService


def _to_decimal(value: float) -> Decimal:
    return Decimal(str(round(value, 2)))


class DocumentRegionService(TenantScopedService[DocumentRegion]):
    resource_type = "document_region"

    def __init__(
        self,
        session: AsyncSession,
        repo: DocumentRegionRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or DocumentRegionRepository(session), audit_service=audit_service
        )

    async def persist_regions(
        self,
        institution_id: uuid.UUID,
        regions: list[DetectedRegion],
        *,
        answer_script_page_id: uuid.UUID | None = None,
        official_exam_document_page_id: uuid.UUID | None = None,
        crop_storage_keys: dict[int, str] | None = None,
        extra_metadata: dict[int, dict[str, Any]] | None = None,
        created_by: uuid.UUID | None = None,
    ) -> list[DocumentRegion]:
        if (answer_script_page_id is None) == (official_exam_document_page_id is None):
            raise ValueError(
                "Exactly one of answer_script_page_id/official_exam_document_page_id must be set."
            )

        crop_storage_keys = crop_storage_keys or {}
        extra_metadata = extra_metadata or {}

        rows = [
            DocumentRegion(
                institution_id=institution_id,
                answer_script_page_id=answer_script_page_id,
                official_exam_document_page_id=official_exam_document_page_id,
                region_type=region.region_type,
                source_label=region.source_label,
                source_detector=region.source_detector,
                reading_order=region.reading_order,
                bbox_left=region.bbox.left,
                bbox_top=region.bbox.top,
                bbox_width=region.bbox.width,
                bbox_height=region.bbox.height,
                confidence=_to_decimal(region.confidence),
                crop_storage_key=crop_storage_keys.get(index),
                extra_metadata=extra_metadata.get(index),
                created_by=created_by,
            )
            for index, region in enumerate(regions)
        ]
        self.session.add_all(rows)
        await self.session.flush()
        return rows
