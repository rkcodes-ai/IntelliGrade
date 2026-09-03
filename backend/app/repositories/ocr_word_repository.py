"""Persistence access for `OCRWord`."""

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ocr_word import OCRWord
from app.repositories.tenant_repository import TenantScopedRepository


class OCRWordRepository(TenantScopedRepository[OCRWord]):
    search_fields = ("text",)
    sortable_fields = ("created_at", "updated_at", "reading_order")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(OCRWord, session)

    async def list_by_lines(
        self, institution_id: uuid.UUID, ocr_line_ids: Sequence[uuid.UUID]
    ) -> list[OCRWord]:
        """All words under a set of `OCRLine`s, ordered by
        `(ocr_line_id, reading_order)` — used by `GET
        /ocr-results/{id}/blocks` to assemble the full tree in three
        queries total (not N+1). See `OCRResultService.get_hierarchy`."""
        if not ocr_line_ids:
            return []
        query = (
            self._base_query(institution_id)
            .where(OCRWord.ocr_line_id.in_(ocr_line_ids))
            .order_by(OCRWord.ocr_line_id.asc(), OCRWord.reading_order.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
