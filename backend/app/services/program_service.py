"""Program management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.program import Program
from app.repositories.department_repository import DepartmentRepository
from app.repositories.program_repository import ProgramRepository
from app.schemas.program import ProgramCreate, ProgramUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class ProgramService(TenantScopedService[Program]):
    resource_type = "program"

    def __init__(
        self,
        session: AsyncSession,
        repo: ProgramRepository | None = None,
        department_repo: DepartmentRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session, repo or ProgramRepository(session), audit_service=audit_service)
        self.department_repo = department_repo or DepartmentRepository(session)

    async def create(
        self, institution_id: uuid.UUID, data: ProgramCreate, *, created_by: uuid.UUID | None
    ) -> Program:
        department = await self.department_repo.get_by_id_for_institution(
            data.department_id, institution_id
        )
        if department is None:
            raise NotFoundError("Department not found.")

        if await self.repo.code_exists(
            institution_id,
            "code",
            data.code,
            scope_conditions=(Program.department_id == data.department_id,),
        ):
            raise ConflictError("A program with that code already exists in this department.")

        program = Program(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        program = await self.repo.add(program)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, program.id)
        return program

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: ProgramUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> Program:
        program = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "department_id" in updates:
            department = await self.department_repo.get_by_id_for_institution(
                updates["department_id"], institution_id
            )
            if department is None:
                raise NotFoundError("Department not found.")

        if "code" in updates:
            target_department_id = updates.get("department_id", program.department_id)
            if await self.repo.code_exists(
                institution_id,
                "code",
                updates["code"],
                exclude_id=entity_id,
                scope_conditions=(Program.department_id == target_department_id,),
            ):
                raise ConflictError("A program with that code already exists in this department.")

        for field, value in updates.items():
            setattr(program, field, value)
        program.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(program)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, program.id)
        return program
