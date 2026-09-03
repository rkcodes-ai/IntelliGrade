"""NotificationEvent endpoints (Module 07, ADR-046) — read/list/mark-read
for the current user only. There is no create endpoint: events are
written internally by the services that trigger them."""

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.notification_event import NotificationEvent
from app.schemas.notification_event import NotificationEventRead
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _to_read(entity: NotificationEvent) -> NotificationEventRead:
    return NotificationEventRead.model_validate(entity)


@router.get(
    "",
    response_model=list[NotificationEventRead],
    dependencies=[Depends(require_permissions(PermissionCode.NOTIFICATIONS_READ))],
)
async def list_my_notifications(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
    unread_only: bool = False,
) -> list[NotificationEventRead]:
    service = NotificationService(db)
    events = await service.list_for_current_user(
        institution_id, current_user.id, unread_only=unread_only
    )
    return [_to_read(e) for e in events]


@router.get(
    "/unread-count",
    dependencies=[Depends(require_permissions(PermissionCode.NOTIFICATIONS_READ))],
)
async def get_unread_notification_count(
    db: DbSession, institution_id: CurrentInstitutionDep, current_user: CurrentUserDep
) -> dict[str, int]:
    service = NotificationService(db)
    count = await service.unread_count(institution_id, current_user.id)
    return {"unread_count": count}


@router.post(
    "/{entity_id}/read",
    response_model=NotificationEventRead,
    dependencies=[Depends(require_permissions(PermissionCode.NOTIFICATIONS_UPDATE))],
)
async def mark_notification_read(
    entity_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> NotificationEventRead:
    service = NotificationService(db)
    entity = await service.mark_read(institution_id, entity_id, actor_id=current_user.id)
    await db.commit()
    return _to_read(entity)
