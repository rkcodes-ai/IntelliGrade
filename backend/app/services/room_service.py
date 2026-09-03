"""Room management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.room import Room
from app.repositories.room_repository import RoomRepository
from app.schemas.room import RoomCreate, RoomUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class RoomService(TenantScopedService[Room]):
    resource_type = "room"

    def __init__(
        self,
        session: AsyncSession,
        repo: RoomRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(session, repo or RoomRepository(session), audit_service=audit_service)

    async def create(
        self, institution_id: uuid.UUID, data: RoomCreate, *, created_by: uuid.UUID | None
    ) -> Room:
        # Import kept local to the method (not module-level) so this file
        # does not need to exist on disk until create() actually runs —
        # Campus is owned by a sibling agent working in the same wave.
        from app.repositories.campus_repository import CampusRepository

        campus = await CampusRepository(self.session).get_by_id_for_institution(
            data.campus_id, institution_id
        )
        if campus is None:
            raise NotFoundError("Campus not found.")

        if await self.repo.code_exists(
            institution_id,
            "name",
            data.name,
            scope_conditions=(Room.campus_id == data.campus_id,),
        ):
            raise ConflictError("A room with that name already exists on this campus.")

        room = Room(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        room = await self.repo.add(room)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, room.id)
        return room

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: RoomUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> Room:
        from app.repositories.campus_repository import CampusRepository

        room = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        target_campus_id = updates.get("campus_id", room.campus_id)

        if "campus_id" in updates:
            campus = await CampusRepository(self.session).get_by_id_for_institution(
                updates["campus_id"], institution_id
            )
            if campus is None:
                raise NotFoundError("Campus not found.")

        if "name" in updates or "campus_id" in updates:
            name_value = updates.get("name", room.name)
            if await self.repo.code_exists(
                institution_id,
                "name",
                name_value,
                exclude_id=entity_id,
                scope_conditions=(Room.campus_id == target_campus_id,),
            ):
                raise ConflictError("A room with that name already exists on this campus.")

        for field, value in updates.items():
            setattr(room, field, value)
        room.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(room)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, room.id)
        return room
