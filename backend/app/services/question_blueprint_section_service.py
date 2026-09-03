"""QuestionBlueprintSection management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError
from app.models.question_blueprint_section import QuestionBlueprintSection
from app.repositories.question_blueprint_repository import QuestionBlueprintRepository
from app.repositories.question_blueprint_section_repository import (
    QuestionBlueprintSectionRepository,
)
from app.schemas.question_blueprint_section import (
    QuestionBlueprintSectionCreate,
    QuestionBlueprintSectionUpdate,
)
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class QuestionBlueprintSectionService(TenantScopedService[QuestionBlueprintSection]):
    resource_type = "question_blueprint_section"

    def __init__(
        self,
        session: AsyncSession,
        repo: QuestionBlueprintSectionRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session,
            repo or QuestionBlueprintSectionRepository(session),
            audit_service=audit_service,
        )

    async def _validate_lookups(
        self, institution_id: uuid.UUID, updates: dict[str, object]
    ) -> None:
        # Local imports: these sibling lookup-table repositories belong to
        # other agents' waves and may not exist on disk yet when this module
        # is first imported — kept local so this file stays importable
        # regardless of import order, exactly like `QuestionService.create`'s
        # lookup-repository imports.
        from app.repositories.bloom_taxonomy_level_repository import BloomTaxonomyLevelRepository
        from app.repositories.difficulty_level_repository import DifficultyLevelRepository
        from app.repositories.question_category_repository import QuestionCategoryRepository
        from app.repositories.question_type_repository import QuestionTypeRepository

        if "question_category_id" in updates and updates["question_category_id"] is not None:
            category = await QuestionCategoryRepository(self.session).get_by_id_for_institution(
                updates["question_category_id"], institution_id  # type: ignore[arg-type]
            )
            if category is None:
                raise NotFoundError("Question category not found.")

        if "difficulty_level_id" in updates and updates["difficulty_level_id"] is not None:
            difficulty_level = await DifficultyLevelRepository(
                self.session
            ).get_by_id_for_institution(
                updates["difficulty_level_id"], institution_id  # type: ignore[arg-type]
            )
            if difficulty_level is None:
                raise NotFoundError("Difficulty level not found.")

        if "bloom_level_id" in updates and updates["bloom_level_id"] is not None:
            bloom_level = await BloomTaxonomyLevelRepository(
                self.session
            ).get_by_id_for_institution(
                updates["bloom_level_id"], institution_id  # type: ignore[arg-type]
            )
            if bloom_level is None:
                raise NotFoundError("Bloom taxonomy level not found.")

        if "question_type_id" in updates and updates["question_type_id"] is not None:
            question_type = await QuestionTypeRepository(self.session).get_by_id_for_institution(
                updates["question_type_id"], institution_id  # type: ignore[arg-type]
            )
            if question_type is None:
                raise NotFoundError("Question type not found.")

    async def create(
        self,
        institution_id: uuid.UUID,
        data: QuestionBlueprintSectionCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> QuestionBlueprintSection:
        blueprint = await QuestionBlueprintRepository(self.session).get_by_id_for_institution(
            data.blueprint_id, institution_id
        )
        if blueprint is None:
            raise NotFoundError("Question blueprint not found.")

        payload = data.model_dump()
        await self._validate_lookups(institution_id, payload)

        section = QuestionBlueprintSection(
            institution_id=institution_id,
            **payload,
            created_by=created_by,
        )
        section = await self.repo.add(section)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, section.id)
        return section

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: QuestionBlueprintSectionUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> QuestionBlueprintSection:
        section = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "blueprint_id" in updates:
            blueprint = await QuestionBlueprintRepository(self.session).get_by_id_for_institution(
                updates["blueprint_id"], institution_id
            )
            if blueprint is None:
                raise NotFoundError("Question blueprint not found.")

        await self._validate_lookups(institution_id, updates)

        for field, value in updates.items():
            setattr(section, field, value)
        section.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(section)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, section.id)
        return section
