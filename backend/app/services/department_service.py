"""Department management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.department import Department
from app.repositories.campus_repository import CampusRepository
from app.repositories.department_repository import DepartmentRepository
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class DepartmentService(TenantScopedService[Department]):
    resource_type = "department"

    def __init__(
        self,
        session: AsyncSession,
        repo: DepartmentRepository | None = None,
        campus_repo: CampusRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or DepartmentRepository(session), audit_service=audit_service
        )
        self.campus_repo = campus_repo or CampusRepository(session)

    async def create(
        self, institution_id: uuid.UUID, data: DepartmentCreate, *, created_by: uuid.UUID | None
    ) -> Department:
        campus = await self.campus_repo.get_by_id_for_institution(data.campus_id, institution_id)
        if campus is None:
            raise NotFoundError("Campus not found.")

        if await self.repo.code_exists(
            institution_id,
            "code",
            data.code,
            scope_conditions=(Department.campus_id == data.campus_id,),
        ):
            raise ConflictError("A department with that code already exists in this campus.")

        department = Department(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        department = await self.repo.add(department)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, department.id)
        return department

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: DepartmentUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> Department:
        department = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "campus_id" in updates:
            campus = await self.campus_repo.get_by_id_for_institution(
                updates["campus_id"], institution_id
            )
            if campus is None:
                raise NotFoundError("Campus not found.")

        if "code" in updates:
            target_campus_id = updates.get("campus_id", department.campus_id)
            if await self.repo.code_exists(
                institution_id,
                "code",
                updates["code"],
                exclude_id=entity_id,
                scope_conditions=(Department.campus_id == target_campus_id,),
            ):
                raise ConflictError("A department with that code already exists in this campus.")

        for field, value in updates.items():
            setattr(department, field, value)
        department.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(department)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, department.id)
        return department
