"""Persistence access for `AnswerScriptPage`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer_script_page import AnswerScriptPage
from app.repositories.tenant_repository import TenantScopedRepository


class AnswerScriptPageRepository(TenantScopedRepository[AnswerScriptPage]):
    sortable_fields = ("page_number", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AnswerScriptPage, session)
