"""ExamSession management service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.exam_session import ExamSession
from app.repositories.exam_session_repository import ExamSessionRepository
from app.schemas.exam_session import ExamSessionCreate, ExamSessionUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantScopedService


class ExamSessionService(TenantScopedService[ExamSession]):
    resource_type = "exam_session"

    def __init__(
        self,
        session: AsyncSession,
        repo: ExamSessionRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        repo = repo or ExamSessionRepository(session)
        super().__init__(session, repo, audit_service=audit_service)
        self._exam_session_repo = repo

    async def create(
        self, institution_id: uuid.UUID, data: ExamSessionCreate, *, created_by: uuid.UUID | None
    ) -> ExamSession:
        # Local import: `ExamRepository` is a same-wave sibling and may not
        # exist on disk yet when this module is first imported — kept local
        # so this file stays importable regardless of import order (same
        # pattern as `class_schedule_service.py`).
        from app.repositories.exam_repository import ExamRepository

        exam = await ExamRepository(self.session).get_by_id_for_institution(
            data.exam_id, institution_id
        )
        if exam is None:
            raise NotFoundError("Exam not found.")

        if await self._exam_session_repo.exists_for_exam_and_student(
            institution_id, data.exam_id, data.student_user_id
        ):
            raise ConflictError("This student already has a session for this exam.")

        session_row = ExamSession(
            institution_id=institution_id,
            **data.model_dump(),
            is_active=True,
            created_by=created_by,
        )
        session_row = await self.repo.add(session_row)
        await self._log_audit(AuditAction.ACADEMIC_ENTITY_CREATED, created_by, session_row.id)
        return session_row

    async def update(
        self,
        institution_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: ExamSessionUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> ExamSession:
        from app.repositories.exam_repository import ExamRepository

        session_row = await self.get_by_id(institution_id, entity_id)
        updates = data.model_dump(exclude_unset=True)

        if "exam_id" in updates:
            exam = await ExamRepository(self.session).get_by_id_for_institution(
                updates["exam_id"], institution_id
            )
            if exam is None:
                raise NotFoundError("Exam not found.")

        if "exam_id" in updates or "student_user_id" in updates:
            target_exam_id = updates.get("exam_id", session_row.exam_id)
            target_student_id = updates.get("student_user_id", session_row.student_user_id)
            if await self._exam_session_repo.exists_for_exam_and_student(
                institution_id, target_exam_id, target_student_id, exclude_id=entity_id
            ):
                raise ConflictError("This student already has a session for this exam.")

        for field, value in updates.items():
            setattr(session_row, field, value)
        session_row.updated_by = updated_by
        await self.session.flush()
        # See TenantScopedService.restore()'s comment: `updated_at` is left
        # expired after an UPDATE flush on SQLite; refresh before this
        # entity is serialized in the response.
        await self.session.refresh(session_row)

        await self._log_audit(AuditAction.ACADEMIC_ENTITY_UPDATED, updated_by, session_row.id)
        return session_row
