"""
AIConfiguration management service.

Business rules enforced here (not in the database): the referenced
`AIProvider` must exist; a non-null `assessment_id` must reference an
existing `Assessment` in the same institution. Mirrors
`app.services.ocr_configuration_service.OCRConfigurationService`'s shape.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError
from app.models.ai_configuration import AIConfiguration
from app.models.ai_provider import AIProvider
from app.repositories.ai_configuration_repository import AIConfigurationRepository
from app.schemas.ai_configuration import AIConfigurationCreate, AIConfigurationUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class AIConfigurationService(TenantScopedService[AIConfiguration]):
    resource_type = "ai_configuration"

    def __init__(
        self,
        session: AsyncSession,
        repo: AIConfigurationRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or AIConfigurationRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: AIConfigurationCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> AIConfiguration:
        provider = await self.session.get(AIProvider, data.ai_provider_id)
        if provider is None:
            raise NotFoundError("AI provider not found.")

        if data.assessment_id is not None:
            # Local import: `Assessment`/`AssessmentRepository` belong to a
            # sibling module and may not exist on disk yet when this module
            # is first imported — kept local so this file stays importable
            # regardless of import order (same pattern as
            # `OCRConfigurationService.create`'s `AssessmentRepository` import).
            from app.repositories.assessment_repository import AssessmentRepository

            assessment = await AssessmentRepository(self.session).get_by_id_for_institution(
                data.assessment_id, institution_id
            )
            if assessment is None:
                raise NotFoundError("Assessment not found.")

        configuration = AIConfiguration(
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
        data: AIConfigurationUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> AIConfiguration:
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
