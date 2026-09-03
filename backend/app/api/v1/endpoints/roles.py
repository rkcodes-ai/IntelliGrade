"""Role listing endpoints. Role/permission *editing* is a future admin-UI concern —
Module 02 seeds the four canonical roles and exposes them read-only via the API."""

from fastapi import APIRouter, Depends

from app.api.deps import DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.schemas.role import RoleRead
from app.services.rbac_service import RBACService

router = APIRouter(prefix="/roles", tags=["Roles"])


@router.get(
    "",
    response_model=list[RoleRead],
    dependencies=[Depends(require_permissions(PermissionCode.ROLES_LIST))],
    summary="List all roles",
)
async def list_roles(db: DbSession) -> list[RoleRead]:
    service = RBACService(db)
    roles = await service.list_roles()
    return [
        RoleRead(
            id=role.id,
            name=role.name,
            description=role.description,
            is_system=role.is_system,
            permissions=[rp.permission.code for rp in role.role_permissions],
        )
        for role in roles
    ]
