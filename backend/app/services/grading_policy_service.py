"""GradingPolicy management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError
from app.models.grading_policy import GradingPolicy
from app.repositories.grading_policy_repository import GradingPolicyRepository
from app.schemas.grading_policy import GradingPolicyCreate, GradingPolicyUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class GradingPolicyService(TenantScopedService[GradingPolicy]):
    resource_type = "grading_policy"

    def __init__(
        self,
        session: AsyncSession,
        repo: GradingPolicyRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or GradingPolicyRepository(session), audit_service=audit_service
        )

    async def create(
        self, institution_id: uuid.UUID, data: GradingPolicyCreate, *, created_by: uuid.UUID | None
    ) -> GradingPolicy:
        if await self.repo.code_exists(institution_id, "name", data.name):
            raise ConflictError("A grading policy with that name already exists.")

        entity = GradingPolicy(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        entity = await self.repo.add(entity)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, entity.id)
        return entity

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: GradingPolicyUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> GradingPolicy:
        entity = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "name" in updates and await self.repo.code_exists(
            institution_id, "name", updates["name"], exclude_id=entity_id
        ):
            raise ConflictError("A grading policy with that name already exists.")

        for field, value in updates.items():
            setattr(entity, field, value)
        entity.updated_by = updated_by
        await self.session.flush()
        # See `SubjectCategoryService.update` for why this refresh is needed
        # (avoids a post-flush `MissingGreenlet` on `updated_at`).
        await self.session.refresh(entity)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, entity.id)
        return entity
