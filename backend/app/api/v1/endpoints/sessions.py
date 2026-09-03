"""Session management endpoints — list and revoke your own logged-in devices."""

import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.schemas.session import SessionRead
from app.services.session_service import SessionService
from app.services.token_service import TokenService

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.get(
    "",
    response_model=list[SessionRead],
    dependencies=[Depends(require_permissions(PermissionCode.SESSIONS_READ))],
    summary="List your active sessions",
)
async def list_sessions(db: DbSession, current_user: CurrentUserDep) -> list[SessionRead]:
    service = SessionService(db)
    sessions = await service.list_for_user(current_user.id)
    return [
        SessionRead(
            id=s.id,
            ip_address=s.ip_address,
            user_agent=s.user_agent,
            device_label=s.device_label,
            is_active=s.is_active,
            last_active_at=s.last_active_at,
            expires_at=s.expires_at,
            created_at=s.created_at,
            is_current=(s.refresh_token_family_id == current_user.session_family_id),
        )
        for s in sessions
    ]


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(PermissionCode.SESSIONS_REVOKE))],
    summary="Revoke one of your sessions",
)
async def revoke_session(
    session_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep
) -> None:
    session_service = SessionService(db)
    family_id = await session_service.revoke(current_user.id, session_id)

    token_service = TokenService(db)
    await token_service.refresh_token_repo.revoke_family(family_id)

    await db.commit()
