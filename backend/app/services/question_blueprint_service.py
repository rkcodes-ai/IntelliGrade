"""QuestionBlueprint management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError
from app.models.question_blueprint import QuestionBlueprint
from app.repositories.question_blueprint_repository import QuestionBlueprintRepository
from app.repositories.subject_repository import SubjectRepository
from app.schemas.question_blueprint import QuestionBlueprintCreate, QuestionBlueprintUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class QuestionBlueprintService(TenantScopedService[QuestionBlueprint]):
    resource_type = "question_blueprint"

    def __init__(
        self,
        session: AsyncSession,
        repo: QuestionBlueprintRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or QuestionBlueprintRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: QuestionBlueprintCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> QuestionBlueprint:
        subject = await SubjectRepository(self.session).get_by_id_for_institution(
            data.subject_id, institution_id
        )
        if subject is None:
            raise NotFoundError("Subject not found.")

        blueprint = QuestionBlueprint(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            current_version=1,
            created_by=created_by,
        )
        blueprint = await self.repo.add(blueprint)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, blueprint.id)
        return blueprint

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: QuestionBlueprintUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> QuestionBlueprint:
        blueprint = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "subject_id" in updates:
            subject = await SubjectRepository(self.session).get_by_id_for_institution(
                updates["subject_id"], institution_id
            )
            if subject is None:
                raise NotFoundError("Subject not found.")

        # A change to the target distribution itself bumps the cheap version
        # counter (see `VersionCounterMixin`) — cosmetic edits (e.g. name)
        # alone do not.
        bump_version = "total_marks" in updates or "total_questions" in updates

        for field, value in updates.items():
            setattr(blueprint, field, value)
        if bump_version:
            blueprint.current_version += 1
        blueprint.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(blueprint)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, blueprint.id)
        return blueprint
