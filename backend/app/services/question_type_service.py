"""QuestionType management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError
from app.models.question_type import QuestionType
from app.repositories.question_type_repository import QuestionTypeRepository
from app.schemas.question_type import QuestionTypeCreate, QuestionTypeUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class QuestionTypeService(TenantScopedService[QuestionType]):
    resource_type = "question_type"

    def __init__(
        self,
        session: AsyncSession,
        repo: QuestionTypeRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or QuestionTypeRepository(session), audit_service=audit_service
        )

    async def create(
        self, institution_id: uuid.UUID, data: QuestionTypeCreate, *, created_by: uuid.UUID | None
    ) -> QuestionType:
        if await self.repo.code_exists(institution_id, "code", data.code):
            raise ConflictError("A question type with that code already exists.")

        entity = QuestionType(
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
        data: QuestionTypeUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> QuestionType:
        entity = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "code" in updates and await self.repo.code_exists(
            institution_id, "code", updates["code"], exclude_id=entity_id
        ):
            raise ConflictError("A question type with that code already exists.")

        for field, value in updates.items():
            setattr(entity, field, value)
        entity.updated_by = updated_by
        await self.session.flush()
        # `updated_at` (onupdate=func.now()) is left expired by the flush on
        # SQLite/aiosqlite (no eager RETURNING fetch on UPDATE) — refresh here,
        # while still inside an awaited session call, so the later synchronous
        # Pydantic read in the router's `_to_read()` doesn't trigger a lazy
        # load outside of greenlet context (`MissingGreenlet`).
        await self.session.refresh(entity)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, entity.id)
        return entity
