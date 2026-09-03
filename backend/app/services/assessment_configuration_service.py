"""
AssessmentConfiguration management service.

Business rules enforced here (not in the database): `assessment_id` must
reference an existing `Assessment` in the same institution, `passing_marks`
must not exceed `maximum_marks`, and at most one configuration may exist per
assessment (the model's `unique=True` on `assessment_id` also enforces this
at the database level; the pre-check here exists to return a clean 409
instead of surfacing a raw integrity-error).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.assessment_configuration import AssessmentConfiguration
from app.repositories.assessment_configuration_repository import AssessmentConfigurationRepository
from app.schemas.assessment_configuration import (
    AssessmentConfigurationCreate,
    AssessmentConfigurationUpdate,
)
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class AssessmentConfigurationService(TenantScopedService[AssessmentConfiguration]):
    resource_type = "assessment_configuration"

    def __init__(
        self,
        session: AsyncSession,
        repo: AssessmentConfigurationRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session,
            repo or AssessmentConfigurationRepository(session),
            audit_service=audit_service,
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: AssessmentConfigurationCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> AssessmentConfiguration:
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

        if data.passing_marks > data.maximum_marks:
            raise ValidationAppError("passing_marks must not exceed maximum_marks.")

        if await self.repo.code_exists(
            institution_id,
            "assessment_id",
            data.assessment_id,  # type: ignore[arg-type] # code_exists's code_value is
            # typed `str` but does a plain `==` comparison, so it works for any column
            # type — see TenantScopedRepository.code_exists docstring.
        ):
            raise ConflictError("An assessment configuration already exists for this assessment.")

        configuration = AssessmentConfiguration(
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
        data: AssessmentConfigurationUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> AssessmentConfiguration:
        configuration = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        target_maximum_marks = updates.get("maximum_marks", configuration.maximum_marks)
        target_passing_marks = updates.get("passing_marks", configuration.passing_marks)
        if target_passing_marks > target_maximum_marks:
            raise ValidationAppError("passing_marks must not exceed maximum_marks.")

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
