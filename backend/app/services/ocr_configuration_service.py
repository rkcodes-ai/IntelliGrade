"""
OCRConfiguration management service.

Business rules enforced here (not in the database): the referenced
`OCRProvider` must exist, be enabled, and be implemented; a non-null
`assessment_id` must reference an existing `Assessment` in the same
institution.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.ocr_configuration import OCRConfiguration
from app.repositories.ocr_configuration_repository import OCRConfigurationRepository
from app.repositories.ocr_provider_repository import OCRProviderRepository
from app.schemas.ocr_configuration import OCRConfigurationCreate, OCRConfigurationUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class OCRConfigurationService(TenantScopedService[OCRConfiguration]):
    resource_type = "ocr_configuration"

    def __init__(
        self,
        session: AsyncSession,
        repo: OCRConfigurationRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or OCRConfigurationRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: OCRConfigurationCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> OCRConfiguration:
        provider = await OCRProviderRepository(self.session).get_by_id(data.ocr_provider_id)
        if provider is None:
            raise NotFoundError("OCR provider not found.")
        if not provider.is_enabled:
            raise ValidationAppError("Selected OCR provider is not enabled.")
        if not provider.is_implemented:
            raise ValidationAppError("Selected OCR provider is not implemented.")

        if data.assessment_id is not None:
            # Local import: `Assessment`/`AssessmentRepository` belong to a
            # sibling module and may not exist on disk yet when this module
            # is first imported — kept local so this file stays importable
            # regardless of import order (same pattern as
            # `AssessmentConfigurationService.create`'s `AssessmentRepository`
            # import).
            from app.repositories.assessment_repository import AssessmentRepository

            assessment = await AssessmentRepository(self.session).get_by_id_for_institution(
                data.assessment_id, institution_id
            )
            if assessment is None:
                raise NotFoundError("Assessment not found.")

        configuration = OCRConfiguration(
            institution_id=institution_id,
            **data.model_dump(),
            created_by=created_by,
        )
        configuration = await self.repo.add(configuration)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, configuration.id)
        return configuration

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: OCRConfigurationUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> OCRConfiguration:
        configuration = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(configuration, field, value)
        configuration.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(configuration)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, configuration.id)
        return configuration
