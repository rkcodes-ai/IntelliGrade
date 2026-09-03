"""
Institution management service.

Not tenant-scoped (Institution IS the tenant root), so this does not
extend `TenantScopedService` — structured the same way as Module 02's
`UserService` instead. `assign_user`/`revoke_user`/`list_members` manage
`UserInstitution` membership rows (see ADR-014).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction, Role
from app.core.exceptions import ConflictError, NotFoundError
from app.core.rbac import CurrentUser
from app.models.institution import Institution
from app.models.user_institution import UserInstitution
from app.repositories.institution_repository import InstitutionRepository
from app.repositories.user_institution_repository import UserInstitutionRepository
from app.schemas.institution import InstitutionCreate, InstitutionUpdate
from app.schemas.pagination import PageParams
from app.services.audit_service import AuditService
from app.services.base import BaseService

RESOURCE_TYPE = "institution"


class InstitutionService(BaseService):
    def __init__(
        self,
        session: AsyncSession,
        repo: InstitutionRepository | None = None,
        membership_repo: UserInstitutionRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session)
        self.repo = repo or InstitutionRepository(session)
        self.membership_repo = membership_repo or UserInstitutionRepository(session)
        self.audit_service = audit_service or AuditService(session)

    async def get_by_id(self, institution_id: uuid.UUID) -> Institution:
        institution = await self.repo.get_by_id(institution_id)
        if institution is None:
            raise NotFoundError("Institution not found.")
        return institution

    async def list_paginated(self, params: PageParams) -> tuple[list[Institution], int]:
        return await self.repo.list_paginated(params)

    async def list_deleted(self, params: PageParams) -> tuple[list[Institution], int]:
        return await self.repo.list_deleted(params)

    async def list_mine(self, current_user: CurrentUser) -> list[Institution]:
        """
        Institutions the current user may select as their active tenant.

        `super_admin` sees every institution (global role, no membership
        row required — see `app.core.tenancy.get_current_institution_id`);
        every other role sees only institutions they hold an active
        `UserInstitution` membership for. Powers the frontend's institution
        switcher.
        """
        if current_user.has_role(Role.SUPER_ADMIN):
            return await self.repo.list_all_active()
        return await self.repo.list_for_user(current_user.id)

    async def create(self, data: InstitutionCreate, *, created_by: uuid.UUID | None) -> Institution:
        if await self.repo.name_exists(data.name):
            raise ConflictError("An institution with that name already exists.")
        if await self.repo.code_exists(data.code):
            raise ConflictError("An institution with that code already exists.")

        institution = Institution(**data.model_dump(), is_active=True, created_by=created_by)
        institution = await self.repo.add(institution)

        await self.audit_service.log(
            action=AuditAction.ACADEMIC_ENTITY_CREATED,
            status="success",
            user_id=created_by,
            resource_type=RESOURCE_TYPE,
            resource_id=str(institution.id),
        )
        return institution

    async def update(
        self, institution_id: uuid.UUID, data: InstitutionUpdate, *, updated_by: uuid.UUID | None
    ) -> Institution:
        institution = await self.get_by_id(institution_id)
        updates = data.model_dump(exclude_unset=True)

        if "name" in updates and await self.repo.name_exists(
            updates["name"], exclude_id=institution_id
        ):
            raise ConflictError("An institution with that name already exists.")

        for field, value in updates.items():
            setattr(institution, field, value)
        institution.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(institution)

        await self.audit_service.log(
            action=AuditAction.ACADEMIC_ENTITY_UPDATED,
            status="success",
            user_id=updated_by,
            resource_type=RESOURCE_TYPE,
            resource_id=str(institution.id),
        )
        return institution

    async def soft_delete(self, institution_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> None:
        institution = await self.get_by_id(institution_id)
        await self.repo.soft_delete(institution, actor_id=actor_id)
        await self.audit_service.log(
            action=AuditAction.ACADEMIC_ENTITY_DELETED,
            status="success",
            user_id=actor_id,
            resource_type=RESOURCE_TYPE,
            resource_id=str(institution_id),
        )

    async def restore(
        self, institution_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> Institution:
        institution = await self.repo.get_by_id_include_deleted(institution_id)
        if institution is None:
            raise NotFoundError("Institution not found.")
        await self.repo.restore(institution, actor_id=actor_id)
        await self.session.refresh(institution)
        await self.audit_service.log(
            action=AuditAction.ACADEMIC_ENTITY_RESTORED,
            status="success",
            user_id=actor_id,
            resource_type=RESOURCE_TYPE,
            resource_id=str(institution_id),
        )
        return institution

    async def list_members(self, institution_id: uuid.UUID) -> list[UserInstitution]:
        await self.get_by_id(institution_id)
        return await self.membership_repo.list_for_institution(institution_id)

    async def assign_user(
        self,
        institution_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        is_primary: bool,
        assigned_by: uuid.UUID | None,
    ) -> UserInstitution:
        await self.get_by_id(institution_id)
        existing = await self.membership_repo.get_membership(user_id, institution_id)
        if existing is not None:
            raise ConflictError("This user already belongs to this institution.")

        membership = UserInstitution(
            user_id=user_id, institution_id=institution_id, is_primary=is_primary, is_active=True
        )
        membership = await self.membership_repo.add(membership)

        await self.audit_service.log(
            action=AuditAction.ACADEMIC_ASSIGNMENT_CREATED,
            status="success",
            user_id=assigned_by,
            resource_type="user_institution",
            resource_id=str(membership.id),
            context={"user_id": str(user_id), "institution_id": str(institution_id)},
        )
        return membership

    async def revoke_user(
        self, institution_id: uuid.UUID, user_id: uuid.UUID, *, revoked_by: uuid.UUID | None
    ) -> None:
        membership = await self.membership_repo.get_membership(user_id, institution_id)
        if membership is None:
            raise NotFoundError("This user does not belong to this institution.")
        membership.is_active = False
        await self.session.flush()

        await self.audit_service.log(
            action=AuditAction.ACADEMIC_ENTITY_DELETED,
            status="success",
            user_id=revoked_by,
            resource_type="user_institution",
            resource_id=str(membership.id),
        )
