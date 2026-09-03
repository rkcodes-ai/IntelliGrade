"""QuestionPaperVersion management service — append-only snapshot history."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.models.question_paper import QuestionPaper
from app.models.question_paper_version import QuestionPaperVersion
from app.repositories.question_paper_version_repository import QuestionPaperVersionRepository
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class QuestionPaperVersionService(TenantScopedService[QuestionPaperVersion]):
    resource_type = "question_paper_version"

    def __init__(
        self,
        session: AsyncSession,
        repo: QuestionPaperVersionRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        repo = repo or QuestionPaperVersionRepository(session)
        super().__init__(session, repo, audit_service=audit_service)
        # `self.repo`'s declared type is the generic `TenantScopedRepository`
        # base (set by `TenantScopedService.__init__`), so it doesn't expose
        # `get_next_version_number` to mypy even though the runtime object
        # is a `QuestionPaperVersionRepository` — keep a narrowly-typed
        # second reference for that call, same pattern as
        # `ClassScheduleService._class_schedule_repo`.
        self._question_paper_version_repo = repo

    @staticmethod
    def _build_snapshot(question_paper: QuestionPaper) -> dict[str, Any]:
        """A plain JSON-serializable snapshot of the parent `QuestionPaper`'s
        current scalar fields — child sections/mappings don't exist as
        files yet in this wave, so they aren't captured here."""
        return {
            "name": question_paper.name,
            "total_marks": str(question_paper.total_marks),
            "approval_status": question_paper.approval_status,
        }

    async def create_snapshot(
        self,
        institution_id: uuid.UUID,
        question_paper: QuestionPaper,
        *,
        change_reason: str | None,
        actor_id: uuid.UUID | None,
    ) -> QuestionPaperVersion:
        version_number = await self._question_paper_version_repo.get_next_version_number(
            institution_id, question_paper.id
        )

        version = QuestionPaperVersion(
            institution_id=institution_id,
            question_paper_id=question_paper.id,
            version_number=version_number,
            snapshot=self._build_snapshot(question_paper),
            change_reason=change_reason,
            changed_by=actor_id,
            created_by=actor_id,
        )
        version = await self.repo.add(version)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, actor_id, version.id)
        return version
