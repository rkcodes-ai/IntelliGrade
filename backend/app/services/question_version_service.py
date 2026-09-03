"""QuestionVersion snapshot service — append-only history for `Question`."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError
from app.models.question_version import QuestionVersion
from app.repositories.question_version_repository import QuestionVersionRepository
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class QuestionVersionService(TenantScopedService[QuestionVersion]):
    resource_type = "question_version"

    def __init__(
        self,
        session: AsyncSession,
        repo: QuestionVersionRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        # Kept as a separately, concretely typed attribute (mirrors
        # `QuestionService._tag_map_repo`) because `get_next_version_number`
        # below isn't part of the generic `TenantScopedRepository` surface
        # that `self.repo` (typed by the base class) exposes.
        version_repo = repo or QuestionVersionRepository(session)
        super().__init__(session, version_repo, audit_service=audit_service)
        self._version_repo = version_repo

    async def create_snapshot(
        self,
        institution_id: uuid.UUID,
        question_id: uuid.UUID,
        change_reason: str | None,
        *,
        created_by: uuid.UUID | None,
    ) -> QuestionVersion:
        """
        Snapshot the *current* live state of `Question` `question_id` into a
        new, immutable `QuestionVersion` row.

        AMBIGUITY FLAGGED FOR REVIEW: the task description for the nested
        `POST /api/v1/questions/{question_id}/versions` endpoint says the
        new row's `version_number` should equal `question.current_version`.
        This method instead assigns `max(existing version_number for this
        question) + 1` (1 for the first snapshot), per this method's own,
        more specific spec (`QuestionVersionRepository.get_next_version_number`).
        The two disagree, and I resolved it in favor of max+1: taking
        `version_number` directly from `question.current_version` would make
        two consecutive snapshots of a question whose content never changed
        in between collide on the `(question_id, version_number)` unique
        constraint (a 409, not a new row) — `current_version` only advances
        on a content-changing `PATCH`, but nothing stops calling this
        snapshot endpoint twice in a row without one. The max+1 approach
        always produces a fresh, strictly increasing version number per
        snapshot, independent of whether the live question changed, which
        also matches "snapshot it twice -> version 1 then 2" from the task's
        own test description.
        """
        # Local import: sibling repository owned by another agent in this
        # wave, kept local so this file stays importable regardless of
        # import order — see `QuestionService.create()`'s comment.
        from app.repositories.question_repository import QuestionRepository

        question = await QuestionRepository(self.session).get_by_id_for_institution(
            question_id, institution_id
        )
        if question is None:
            raise NotFoundError("Question not found.")

        next_version_number = await self._version_repo.get_next_version_number(question_id)

        version = QuestionVersion(
            institution_id=institution_id,
            question_id=question.id,
            version_number=next_version_number,
            question_text=question.question_text,
            marks=question.marks,
            difficulty_level_id=question.difficulty_level_id,
            change_reason=change_reason,
            changed_by=created_by,
            created_by=created_by,
        )
        version = await self.repo.add(version)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, version.id)
        return version
