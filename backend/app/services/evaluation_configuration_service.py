"""
EvaluationConfiguration management service.

Business rules enforced here (not in the database): `assessment_id` must
reference an existing `Assessment` in the same institution, and at most one
configuration may exist per assessment (the model's `unique=True` on
`assessment_id` also enforces this at the database level; the pre-check here
exists to return a clean 409 instead of surfacing a raw integrity-error).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.evaluation_configuration import EvaluationConfiguration
from app.repositories.evaluation_configuration_repository import EvaluationConfigurationRepository
from app.schemas.evaluation_configuration import (
    EvaluationConfigurationCreate,
    EvaluationConfigurationUpdate,
)
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class EvaluationConfigurationService(TenantScopedService[EvaluationConfiguration]):
    resource_type = "evaluation_configuration"

    def __init__(
        self,
        session: AsyncSession,
        repo: EvaluationConfigurationRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session,
            repo or EvaluationConfigurationRepository(session),
            audit_service=audit_service,
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: EvaluationConfigurationCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> EvaluationConfiguration:
        # Local import: `Assessment`/`AssessmentRepository` are owned by a
        # sibling agent in this same wave and may not exist on disk yet when
        # this module is first imported — kept local so this file stays
        # importable regardless of import order (same pattern as
        # `ClassScheduleService.create`'s `SubjectAllocationRepository` import).
        from app.repositories.assessment_repository import AssessmentRepository

        assessment = await AssessmentRepository(self.session).get_by_id_for_institution(
            data.assessment_id, institution_id
        )
        if assessment is None:
            raise NotFoundError("Assessment not found.")

        if await self.repo.code_exists(
            institution_id,
            "assessment_id",
            data.assessment_id,  # type: ignore[arg-type] # code_exists's code_value is
            # typed `str` but does a plain `==` comparison, so it works for any column
            # type — see TenantScopedRepository.code_exists docstring.
        ):
            raise ConflictError("An evaluation configuration already exists for this assessment.")

        configuration = EvaluationConfiguration(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        configuration = await self.repo.add(configuration)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, configuration.id)
        return configuration

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: EvaluationConfigurationUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> EvaluationConfiguration:
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
