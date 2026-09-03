"""AttendancePolicy management service."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, ValidationAppError
from app.models.attendance_policy import AttendancePolicy
from app.repositories.attendance_policy_repository import AttendancePolicyRepository
from app.schemas.attendance_policy import AttendancePolicyCreate, AttendancePolicyUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


def _assert_condonation_within_minimum(
    minimum_attendance_percentage: Decimal, condonation_percentage: Decimal | None
) -> None:
    if (
        condonation_percentage is not None
        and condonation_percentage > minimum_attendance_percentage
    ):
        raise ValidationAppError(
            "condonation_percentage cannot exceed minimum_attendance_percentage."
        )


class AttendancePolicyService(TenantScopedService[AttendancePolicy]):
    resource_type = "attendance_policy"

    def __init__(
        self,
        session: AsyncSession,
        repo: AttendancePolicyRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or AttendancePolicyRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: AttendancePolicyCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> AttendancePolicy:
        if await self.repo.code_exists(institution_id, "name", data.name):
            raise ConflictError("An attendance policy with that name already exists.")

        _assert_condonation_within_minimum(
            data.minimum_attendance_percentage, data.condonation_percentage
        )

        entity = AttendancePolicy(
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
        data: AttendancePolicyUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> AttendancePolicy:
        entity = await self.get_by_id(institution_id, entity_id)
        updates: dict[str, Any] = data.model_dump(exclude_unset=True)

        if "name" in updates and await self.repo.code_exists(
            institution_id, "name", updates["name"], exclude_id=entity_id
        ):
            raise ConflictError("An attendance policy with that name already exists.")

        target_minimum = updates.get(
            "minimum_attendance_percentage", entity.minimum_attendance_percentage
        )
        target_condonation = updates.get("condonation_percentage", entity.condonation_percentage)
        if "minimum_attendance_percentage" in updates or "condonation_percentage" in updates:
            _assert_condonation_within_minimum(target_minimum, target_condonation)

        for field, value in updates.items():
            setattr(entity, field, value)
        entity.updated_by = updated_by
        await self.session.flush()
        # See `SubjectCategoryService.update` for why this refresh is needed
        # (avoids a post-flush `MissingGreenlet` on `updated_at`).
        await self.session.refresh(entity)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, entity.id)
        return entity
