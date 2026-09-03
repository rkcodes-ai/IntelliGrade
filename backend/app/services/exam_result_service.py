"""Result Finalization & Locking orchestration (Module 07). See ADR-042.

`ExamResultService` owns the one validated state machine required by
Feature 4/5: `draft -> under_review -> approved -> locked -> published`,
plus an explicit `unlock` transition back to `draft`. A session's
`ExamResult` row is created lazily by the first finalization action.
Once `locked`/`published`, `AnswerEvaluationService` (via
`_ensure_not_locked`) refuses further per-question edits for that
session until this service's `unlock()` runs.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import AppError, ConflictError, NotFoundError, ValidationAppError
from app.models.answer_evaluation import AnswerEvaluation
from app.models.exam import Exam
from app.models.exam_result import ExamResult
from app.models.exam_session import ExamSession
from app.models.student_enrollment import StudentEnrollment
from app.repositories.exam_result_repository import ExamResultRepository
from app.schemas.exam_result import BulkActionFailure, BulkActionResult
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.tenant_service import TenantScopedService

#: Required prior status for each forward transition (ADR-042).
_REQUIRED_PRIOR_STATUS = {
    "approve": "under_review",
    "lock": "approved",
    "publish": "locked",
}


class ExamResultService(TenantScopedService[ExamResult]):
    resource_type = "exam_result"

    def __init__(
        self,
        session: AsyncSession,
        repo: ExamResultRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        repo = repo or ExamResultRepository(session)
        super().__init__(session, repo, audit_service=audit_service)
        self._result_repo = repo
        self._notification_service = NotificationService(session, audit_service=self.audit_service)

    async def _compute_totals(
        self, institution_id: uuid.UUID, exam_session_id: uuid.UUID
    ) -> tuple[Decimal, Decimal]:
        query = select(AnswerEvaluation).where(
            AnswerEvaluation.institution_id == institution_id,
            AnswerEvaluation.exam_session_id == exam_session_id,
            AnswerEvaluation.deleted_at.is_(None),
        )
        evaluations = list((await self.session.execute(query)).scalars().all())
        if not evaluations:
            raise ValidationAppError(
                "This exam session has no evaluated questions yet — nothing to finalize."
            )
        unresolved = [e for e in evaluations if e.final_marks is None]
        if unresolved:
            raise ValidationAppError(
                f"{len(unresolved)} of {len(evaluations)} question(s) still need teacher "
                "review (confirm/override/reject) before this result can be finalized."
            )
        total_max = sum((e.max_marks for e in evaluations), Decimal("0"))
        total_final = sum(
            (e.final_marks for e in evaluations if e.final_marks is not None), Decimal("0")
        )
        return total_max, total_final

    async def finalize_student(
        self, institution_id: uuid.UUID, exam_session_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> ExamResult:
        exam_session = await self.session.get(ExamSession, exam_session_id)
        if exam_session is None or exam_session.institution_id != institution_id:
            raise NotFoundError("Exam session not found.")

        exam_result = await self._result_repo.get_by_exam_session(institution_id, exam_session_id)
        if exam_result is not None and exam_result.status not in ("draft", "under_review"):
            raise ConflictError(
                f"This result is already {exam_result.status} — unlock it before re-finalizing."
            )

        total_max, total_final = await self._compute_totals(institution_id, exam_session_id)
        now = datetime.now(UTC)

        if exam_result is None:
            exam_result = ExamResult(
                institution_id=institution_id,
                exam_session_id=exam_session_id,
                created_by=actor_id,
            )
            self.session.add(exam_result)

        exam_result.status = "under_review"
        exam_result.total_max_marks = total_max
        exam_result.total_marks = total_final
        exam_result.finalized_by = actor_id
        exam_result.finalized_at = now
        exam_result.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(exam_result)
        await self._log_audit(AuditAction.EXAM_RESULT_FINALIZED, actor_id, exam_result.id)
        return exam_result

    async def _exam_session_ids_for_exam(
        self, institution_id: uuid.UUID, exam_id: uuid.UUID
    ) -> list[uuid.UUID]:
        exam = await self.session.get(Exam, exam_id)
        if exam is None or exam.institution_id != institution_id:
            raise NotFoundError("Exam not found.")
        query = select(ExamSession.id).where(
            ExamSession.institution_id == institution_id,
            ExamSession.exam_id == exam_id,
            ExamSession.deleted_at.is_(None),
        )
        return list((await self.session.execute(query)).scalars().all())

    async def finalize_exam(
        self, institution_id: uuid.UUID, exam_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> BulkActionResult:
        session_ids = await self._exam_session_ids_for_exam(institution_id, exam_id)
        return await self._bulk_finalize(institution_id, session_ids, actor_id=actor_id)

    async def finalize_batch(
        self,
        institution_id: uuid.UUID,
        exam_id: uuid.UUID,
        batch_id: uuid.UUID,
        *,
        actor_id: uuid.UUID | None,
    ) -> BulkActionResult:
        exam = await self.session.get(Exam, exam_id)
        if exam is None or exam.institution_id != institution_id:
            raise NotFoundError("Exam not found.")
        student_query = select(StudentEnrollment.student_user_id).where(
            StudentEnrollment.institution_id == institution_id,
            StudentEnrollment.batch_id == batch_id,
            StudentEnrollment.deleted_at.is_(None),
        )
        student_ids = list((await self.session.execute(student_query)).scalars().all())
        if not student_ids:
            raise NotFoundError("No students found enrolled in this batch.")

        session_query = select(ExamSession.id).where(
            ExamSession.institution_id == institution_id,
            ExamSession.exam_id == exam_id,
            ExamSession.student_user_id.in_(student_ids),
            ExamSession.deleted_at.is_(None),
        )
        session_ids = list((await self.session.execute(session_query)).scalars().all())
        return await self._bulk_finalize(institution_id, session_ids, actor_id=actor_id)

    async def _bulk_finalize(
        self,
        institution_id: uuid.UUID,
        exam_session_ids: list[uuid.UUID],
        *,
        actor_id: uuid.UUID | None,
    ) -> BulkActionResult:
        succeeded = 0
        failed: list[BulkActionFailure] = []
        for session_id in exam_session_ids:
            try:
                await self.finalize_student(institution_id, session_id, actor_id=actor_id)
                succeeded += 1
            except AppError as exc:
                failed.append(BulkActionFailure(reference_id=session_id, reason=exc.message))
        return BulkActionResult(succeeded_count=succeeded, failed=failed)

    async def approve(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> ExamResult:
        return await self._transition(
            institution_id,
            entity_id,
            action="approve",
            new_status="approved",
            stamp_field="approved",
            audit_action=AuditAction.EXAM_RESULT_APPROVED,
            actor_id=actor_id,
        )

    async def lock(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> ExamResult:
        return await self._transition(
            institution_id,
            entity_id,
            action="lock",
            new_status="locked",
            stamp_field="locked",
            audit_action=AuditAction.EXAM_RESULT_LOCKED,
            actor_id=actor_id,
        )

    async def publish(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> ExamResult:
        exam_result = await self._transition(
            institution_id,
            entity_id,
            action="publish",
            new_status="published",
            stamp_field="published",
            audit_action=AuditAction.EXAM_RESULT_PUBLISHED,
            actor_id=actor_id,
        )
        exam_session = await self.session.get(ExamSession, exam_result.exam_session_id)
        if exam_session is not None:
            await self._notification_service.create(
                institution_id,
                recipient_user_id=exam_session.student_user_id,
                event_type="result_published",
                payload={
                    "exam_result_id": str(exam_result.id),
                    "exam_session_id": str(exam_result.exam_session_id),
                    "total_marks": str(exam_result.total_marks),
                    "total_max_marks": str(exam_result.total_max_marks),
                },
                actor_id=actor_id,
            )
        return exam_result

    async def unlock(
        self, institution_id: uuid.UUID, entity_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> ExamResult:
        exam_result = await self.get_by_id(institution_id, entity_id)
        if exam_result.status not in ("locked", "published"):
            raise ConflictError(
                "Only a locked or published result can be unlocked "
                f"(currently {exam_result.status})."
            )
        exam_result.status = "draft"
        exam_result.unlocked_by = actor_id
        exam_result.unlocked_at = datetime.now(UTC)
        exam_result.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(exam_result)
        await self._log_audit(AuditAction.EXAM_RESULT_UNLOCKED, actor_id, exam_result.id)
        return exam_result

    async def _transition(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        *,
        action: str,
        new_status: str,
        stamp_field: str,
        audit_action: AuditAction,
        actor_id: uuid.UUID | None,
    ) -> ExamResult:
        exam_result = await self.get_by_id(institution_id, entity_id)
        required_prior = _REQUIRED_PRIOR_STATUS[action]
        if exam_result.status != required_prior:
            raise ConflictError(
                f"Cannot {action} a result that is {exam_result.status} "
                f"(requires {required_prior})."
            )
        exam_result.status = new_status
        setattr(exam_result, f"{stamp_field}_by", actor_id)
        setattr(exam_result, f"{stamp_field}_at", datetime.now(UTC))
        exam_result.updated_by = actor_id
        await self.session.flush()
        await self.session.refresh(exam_result)
        await self._log_audit(audit_action, actor_id, exam_result.id)
        return exam_result

    async def bulk_transition(
        self,
        institution_id: uuid.UUID,
        exam_id: uuid.UUID,
        *,
        action: str,
        actor_id: uuid.UUID | None,
    ) -> BulkActionResult:
        """Feature 11's bulk approval/lock/publish — every `ExamResult` for
        this exam currently in the required prior status is transitioned;
        anything else is reported back as a failure, never silently
        skipped."""
        session_ids = await self._exam_session_ids_for_exam(institution_id, exam_id)
        transition_fn = {"approve": self.approve, "lock": self.lock, "publish": self.publish}[
            action
        ]
        succeeded = 0
        failed: list[BulkActionFailure] = []
        for session_id in session_ids:
            exam_result = await self._result_repo.get_by_exam_session(institution_id, session_id)
            if exam_result is None:
                failed.append(
                    BulkActionFailure(reference_id=session_id, reason="Not yet finalized.")
                )
                continue
            try:
                await transition_fn(institution_id, exam_result.id, actor_id=actor_id)
                succeeded += 1
            except AppError as exc:
                failed.append(BulkActionFailure(reference_id=exam_result.id, reason=exc.message))
        return BulkActionResult(succeeded_count=succeeded, failed=failed)
