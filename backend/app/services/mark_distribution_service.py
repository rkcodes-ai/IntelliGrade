"""
MarkDistribution management service.

Business rules enforced here (not the database): `rubric_criterion_id` must
reference an existing `RubricCriterion` in the same institution, and
`min_score` must not exceed `max_score`.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.mark_distribution import MarkDistribution
from app.repositories.mark_distribution_repository import MarkDistributionRepository
from app.repositories.rubric_criterion_repository import RubricCriterionRepository
from app.schemas.mark_distribution import MarkDistributionCreate, MarkDistributionUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class MarkDistributionService(TenantScopedService[MarkDistribution]):
    resource_type = "mark_distribution"

    def __init__(
        self,
        session: AsyncSession,
        repo: MarkDistributionRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or MarkDistributionRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: MarkDistributionCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> MarkDistribution:
        criterion = await RubricCriterionRepository(self.session).get_by_id_for_institution(
            data.rubric_criterion_id, institution_id
        )
        if criterion is None:
            raise NotFoundError("Rubric criterion not found.")

        if data.min_score > data.max_score:
            raise ValidationAppError("min_score must not exceed max_score.")

        distribution = MarkDistribution(
            institution_id=institution_id,
            **data.model_dump(),
            created_by=created_by,
        )
        distribution = await self.repo.add(distribution)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, distribution.id)
        return distribution

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: MarkDistributionUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> MarkDistribution:
        distribution = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        target_min = updates.get("min_score", distribution.min_score)
        target_max = updates.get("max_score", distribution.max_score)
        if target_min > target_max:
            raise ValidationAppError("min_score must not exceed max_score.")

        for field, value in updates.items():
            setattr(distribution, field, value)
        distribution.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(distribution)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, distribution.id)
        return distribution
