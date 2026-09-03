"""Persistence access for `OCRLine`."""

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ocr_line import OCRLine
from app.repositories.tenant_repository import TenantScopedRepository


class OCRLineRepository(TenantScopedRepository[OCRLine]):
    search_fields = ("text",)
    sortable_fields = ("created_at", "updated_at", "reading_order")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(OCRLine, session)

    async def list_by_blocks(
        self, institution_id: uuid.UUID, ocr_block_ids: Sequence[uuid.UUID]
    ) -> list[OCRLine]:
        """All lines under a set of `OCRBlock`s, ordered by
        `(ocr_block_id, reading_order)` — used by `GET
        /ocr-results/{id}/blocks` to assemble the full tree in three
        queries total (not N+1). See `OCRResultService.get_hierarchy`."""
        if not ocr_block_ids:
            return []
        query = (
            self._base_query(institution_id)
            .where(OCRLine.ocr_block_id.in_(ocr_block_ids))
            .order_by(OCRLine.ocr_block_id.asc(), OCRLine.reading_order.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
