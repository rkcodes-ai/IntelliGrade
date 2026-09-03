"""
AnswerScriptPage service. `create()` is not exposed via any client-facing
route — pages are written internally by `app.tasks.ocr_tasks` during Stage
4/6 (page-splitting), one row per physical page produced from the parent
`AnswerScript`'s original file.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer_script_page import AnswerScriptPage
from app.repositories.answer_script_page_repository import AnswerScriptPageRepository
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class AnswerScriptPageService(TenantScopedService[AnswerScriptPage]):
    resource_type = "answer_script_page"

    def __init__(
        self,
        session: AsyncSession,
        repo: AnswerScriptPageRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or AnswerScriptPageRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        answer_script_id: uuid.UUID,
        *,
        page_number: int,
        storage_key: str | None = None,
        preprocessed_storage_key: str | None = None,
        width_px: int | None = None,
        height_px: int | None = None,
        is_blank: bool = False,
        quality_score: Decimal | None = None,
        quality_classification: str | None = None,
        quality_metrics: dict[str, Any] | None = None,
        enhancement_metadata: dict[str, Any] | None = None,
        created_by: uuid.UUID | None = None,
    ) -> AnswerScriptPage:
        page = AnswerScriptPage(
            institution_id=institution_id,
            answer_script_id=answer_script_id,
            page_number=page_number,
            storage_key=storage_key,
            preprocessed_storage_key=preprocessed_storage_key,
            width_px=width_px,
            height_px=height_px,
            is_blank=is_blank,
            quality_score=quality_score,
            quality_classification=quality_classification,
            quality_metrics=quality_metrics,
            enhancement_metadata=enhancement_metadata,
            status="pending",
            created_by=created_by,
        )
        return await self.repo.add(page)
