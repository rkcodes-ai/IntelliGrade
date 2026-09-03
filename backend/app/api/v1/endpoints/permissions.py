"""Permission listing endpoint — read-only, seeded by migration."""

from fastapi import APIRouter, Depends

from app.api.deps import DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.repositories.permission_repository import PermissionRepository
from app.schemas.permission import PermissionRead

router = APIRouter(prefix="/permissions", tags=["Permissions"])


@router.get(
    "",
    response_model=list[PermissionRead],
    dependencies=[Depends(require_permissions(PermissionCode.PERMISSIONS_LIST))],
    summary="List all permissions",
)
async def list_permissions(db: DbSession) -> list[PermissionRead]:
    repo = PermissionRepository(db)
    permissions = await repo.list_all()
    return [PermissionRead.model_validate(p) for p in permissions]
