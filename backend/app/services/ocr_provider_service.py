"""
OCRProvider management service — global OCR engine catalog (ADR-028).

Business rules enforced here (not in the database): at most one provider may
be the system default at a time, and a provider cannot be enabled unless it
is implemented (a catalog entry may exist for an engine with no adapter
yet — see `OCRProviderNotImplementedError`, ADR-032).
"""

import uuid

from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ValidationAppError
from app.models.ocr_provider import OCRProvider
from app.repositories.ocr_provider_repository import OCRProviderRepository
from app.schemas.ocr_provider import OCRProviderUpdate
from app.services.audit_service import AuditService
from app.services.global_service import GlobalService


class OCRProviderService(GlobalService[OCRProvider]):
    resource_type = "ocr_provider"

    def __init__(
        self,
        session: AsyncSession,
        repo: OCRProviderRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or OCRProviderRepository(session), audit_service=audit_service
        )

    async def update(
        self,
        entity_id: uuid.UUID,
        data: OCRProviderUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> OCRProvider:
        provider = await self.get_by_id(entity_id)
        updates = data.model_dump(exclude_unset=True)

        if updates.get("is_enabled") is True and not provider.is_implemented:
            raise ValidationAppError("Cannot enable an unimplemented OCR provider.")

        if updates.get("is_default") is True:
            # Clear every other row's default flag first -- only one default
            # provider may exist at a time.
            await self.session.execute(
                sa_update(OCRProvider).where(OCRProvider.id != entity_id).values(is_default=False)
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
