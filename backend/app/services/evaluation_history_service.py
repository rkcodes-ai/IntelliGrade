"""EvaluationHistory management service.

Append-only in practice: `create()` is the only mutation this entity's
routes expose (see `app/api/v1/endpoints/evaluation_history.py`; there is
no `EVALUATION_HISTORY_UPDATE`/`DELETE` permission code). `soft_delete()`/
`restore()` are still inherited from `TenantScopedService` for consistency
with every other Assessment Domain entity, even though no route reaches
them.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError
from app.models.evaluation_history import EvaluationHistory
from app.repositories.evaluation_history_repository import EvaluationHistoryRepository
from app.schemas.evaluation_history import EvaluationHistoryCreate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class EvaluationHistoryService(TenantScopedService[EvaluationHistory]):
    resource_type = "evaluation_history"

    def __init__(
        self,
        session: AsyncSession,
        repo: EvaluationHistoryRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or EvaluationHistoryRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: EvaluationHistoryCreate,
        *,
        created_by: uuid.UUID | None,
    ) -> EvaluationHistory:
        # Local import: ExamSession is owned by a sibling agent in this
        # same wave and may not exist on disk yet when this module is first
        # imported — kept local so this file stays importable regardless of
        # import order, same pattern as `class_schedule_service.py`.
        from app.repositories.exam_session_repository import ExamSessionRepository

        exam_session = await ExamSessionRepository(self.session).get_by_id_for_institution(
            data.exam_session_id, institution_id
        )
        if exam_session is None:
            raise NotFoundError("Exam session not found.")

        history = EvaluationHistory(
            institution_id=institution_id,
            **data.model_dump(),
            created_by=created_by,
        )
        history = await self.repo.add(history)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, history.id)
        return history
