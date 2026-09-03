"""
AIProvider management service — global AI evaluation engine catalog.

Business rules enforced here (not in the database): at most one provider may
be the system default at a time, and a provider cannot be enabled unless it
is implemented. Mirrors `app.services.ocr_provider_service.OCRProviderService`
exactly.
"""

import uuid

from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ValidationAppError
from app.models.ai_provider import AIProvider
from app.repositories.ai_provider_repository import AIProviderRepository
from app.schemas.ai_provider import AIProviderUpdate
from app.services.audit_service import AuditService
from app.services.global_service import GlobalService


class AIProviderService(GlobalService[AIProvider]):
    resource_type = "ai_provider"

    def __init__(
        self,
        session: AsyncSession,
        repo: AIProviderRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or AIProviderRepository(session), audit_service=audit_service
        )

    async def update(
        self,
        entity_id: uuid.UUID,
        data: AIProviderUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> AIProvider:
        provider = await self.get_by_id(entity_id)
        updates = data.model_dump(exclude_unset=True)

        if updates.get("is_enabled") is True and not provider.is_implemented:
            raise ValidationAppError("Cannot enable an unimplemented AI provider.")

        if updates.get("is_default") is True:
            # Clear every other row's default flag first -- only one default
            # provider may exist at a time.
            await self.session.execute(
                sa_update(AIProvider).where(AIProvider.id != entity_id).values(is_default=False)
            )

        for field, value in updates.items():
            setattr(provider, field, value)
        provider.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(provider)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, provider.id)
        return provider
