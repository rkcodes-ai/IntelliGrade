"""
RubricCriterion management service.

Business rules enforced here (not the database): `rubric_id` must reference
an existing `Rubric` in the same institution, and if `parent_criterion_id`
is set it must both exist for this institution AND belong to the same
`rubric_id` — a sub-criterion cannot be reparented across rubrics.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.rubric_criterion import RubricCriterion
from app.repositories.rubric_criterion_repository import RubricCriterionRepository
from app.repositories.rubric_repository import RubricRepository
from app.schemas.rubric_criterion import RubricCriterionCreate, RubricCriterionUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class RubricCriterionService(TenantScopedService[RubricCriterion]):
    resource_type = "rubric_criterion"

    def __init__(
        self,
        session: AsyncSession,
        repo: RubricCriterionRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or RubricCriterionRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: RubricCriterionCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> RubricCriterion:
        rubric = await RubricRepository(self.session).get_by_id_for_institution(
            data.rubric_id, institution_id
        )
        if rubric is None:
            raise NotFoundError("Rubric not found.")

        if data.parent_criterion_id is not None:
            parent = await self.repo.get_by_id_for_institution(
                data.parent_criterion_id, institution_id
            )
            if parent is None:
                raise NotFoundError("Parent criterion not found.")
            if parent.rubric_id != data.rubric_id:
                raise ValidationAppError("parent_criterion_id must belong to the same rubric_id.")

        criterion = RubricCriterion(
            institution_id=institution_id,
            **data.model_dump(),
            created_by=created_by,
        )
        criterion = await self.repo.add(criterion)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, criterion.id)
        return criterion

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: RubricCriterionUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> RubricCriterion:
        criterion = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "parent_criterion_id" in updates and updates["parent_criterion_id"] is not None:
            parent = await self.repo.get_by_id_for_institution(
                updates["parent_criterion_id"], institution_id
            )
            if parent is None:
                raise NotFoundError("Parent criterion not found.")
            if parent.rubric_id != criterion.rubric_id:
                raise ValidationAppError("parent_criterion_id must belong to the same rubric_id.")

        for field, value in updates.items():
            setattr(criterion, field, value)
        criterion.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(criterion)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, criterion.id)
        return criterion
