"""
QuestionApproval management service — the formal approve/reject decision audit trail.

INTEGRATION FLAG FOR THE CENTRAL INTEGRATION PASS: `QuestionService.approve()`
and `QuestionService.reject()` (`app/services/question_service.py`, already-
merged Wave 1 code, intentionally NOT modified by this file) currently do
*not* call `record()` below, so approving/rejecting a `Question` today does
not yet leave a `QuestionApproval` audit row behind. Wiring
`QuestionService.approve()`/`reject()` to call
`QuestionApprovalService.record(...)` is a natural follow-up integration
step once every Module 04 entity has landed.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError
from app.models.question_approval import QuestionApproval
from app.repositories.question_approval_repository import QuestionApprovalRepository
from app.schemas.question_approval import ApprovalDecision, QuestionApprovalCreate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class QuestionApprovalService(TenantScopedService[QuestionApproval]):
    resource_type = "question_approval"

    def __init__(
        self,
        session: AsyncSession,
        repo: QuestionApprovalRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        super().__init__(
            session, repo or QuestionApprovalRepository(session), audit_service=audit_service
        )

    async def create(
        self,
        institution_id: uuid.UUID,
        data: QuestionApprovalCreate,
        *,
        reviewed_by: uuid.UUID | None,
    ) -> QuestionApproval:
        # Local imports: sibling repositories, see `QuestionService.create()`'s comment.
        from app.repositories.question_repository import QuestionRepository
        from app.repositories.question_version_repository import QuestionVersionRepository

        question = await QuestionRepository(self.session).get_by_id_for_institution(
            data.question_id, institution_id
        )
        if question is None:
            raise NotFoundError("Question not found.")

        if data.question_version_id is not None:
            version = await QuestionVersionRepository(self.session).get_by_id_for_institution(
                data.question_version_id, institution_id
            )
            if version is None:
                raise NotFoundError("Question version not found.")

        approval = QuestionApproval(
            institution_id=institution_id,
            question_id=data.question_id,
            question_version_id=data.question_version_id,
            decision=data.decision,
            reviewed_by=reviewed_by,
            comments=data.comments,
            created_by=reviewed_by,
        )
        approval = await self.repo.add(approval)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, reviewed_by, approval.id)
        return approval

    async def record(
        self,
        institution_id: uuid.UUID,
        question_id: uuid.UUID,
        decision: ApprovalDecision,
        *,
        reviewed_by: uuid.UUID | None,
        comments: str | None = None,
    ) -> QuestionApproval:
        """
        Convenience wrapper around `create()` with a flatter signature,
        meant to be called directly by another service (e.g. the future
        `QuestionService.approve()`/`reject()` integration flagged in this
        module's docstring) without building a `QuestionApprovalCreate`
        payload by hand.
        """
        data = QuestionApprovalCreate(question_id=question_id, decision=decision, comments=comments)
        return await self.create(institution_id, data, reviewed_by=reviewed_by)
