"""Persistence access for `OCRBlock`."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ocr_block import OCRBlock
from app.repositories.tenant_repository import TenantScopedRepository


class OCRBlockRepository(TenantScopedRepository[OCRBlock]):
    search_fields = ("block_type",)
    sortable_fields = ("created_at", "updated_at", "reading_order")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(OCRBlock, session)

    async def list_by_result(
        self, institution_id: uuid.UUID, ocr_result_id: uuid.UUID
    ) -> list[OCRBlock]:
        """All blocks under one `OCRResult`, ordered by `reading_order` —
        used by `GET /ocr-results/{id}/blocks` to assemble the full tree in
        three queries total (not N+1). See `OCRResultService.get_hierarchy`.
        """
        query = (
            self._base_query(institution_id)
            .where(OCRBlock.ocr_result_id == ocr_result_id)
            .order_by(OCRBlock.reading_order.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
