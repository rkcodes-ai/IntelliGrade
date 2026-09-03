"""Teacher Review Dashboard (Module 07, Feature 1).

Read-only aggregation over `AnswerEvaluation`, joined through the
existing Module 03/04 hierarchy (`Exam -> Assessment -> Subject ->
Course -> Program -> Department`) for the filter set the brief asks for.
No new persisted rollup — see ADR-044 for why this is computed on demand.
"""

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer_evaluation import AnswerEvaluation
from app.models.assessment import Assessment
from app.models.course import Course
from app.models.exam import Exam
from app.models.exam_session import ExamSession
from app.models.program import Program
from app.models.subject import Subject
from app.schemas.pagination import PageParams
from app.schemas.teacher_review import TeacherReviewDashboardSummary, TeacherReviewFilters


class TeacherReviewDashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _filtered_query(
        self, institution_id: uuid.UUID, filters: TeacherReviewFilters
    ) -> Select[tuple[AnswerEvaluation]]:
        query: Select[tuple[AnswerEvaluation]] = select(AnswerEvaluation).where(
            AnswerEvaluation.institution_id == institution_id,
            AnswerEvaluation.deleted_at.is_(None),
        )
        needs_hierarchy = any(
            (filters.exam_id, filters.subject_id, filters.course_id, filters.department_id)
        )
        if needs_hierarchy or filters.student_user_id:
            query = query.join(ExamSession, ExamSession.id == AnswerEvaluation.exam_session_id)
            if filters.student_user_id:
                query = query.where(ExamSession.student_user_id == filters.student_user_id)
        if needs_hierarchy:
            query = (
                query.join(Exam, Exam.id == ExamSession.exam_id)
                .join(Assessment, Assessment.id == Exam.assessment_id)
                .join(Subject, Subject.id == Assessment.subject_id)
                .join(Course, Course.id == Subject.course_id)
                .join(Program, Program.id == Course.program_id)
            )
            if filters.exam_id:
                query = query.where(Exam.id == filters.exam_id)
            if filters.subject_id:
                query = query.where(Subject.id == filters.subject_id)
            if filters.course_id:
                query = query.where(Course.id == filters.course_id)
            if filters.department_id:
                query = query.where(Program.department_id == filters.department_id)
        if filters.confidence_tier:
            query = query.where(AnswerEvaluation.confidence_tier == filters.confidence_tier)
        if filters.review_status:
            query = query.where(AnswerEvaluation.review_status == filters.review_status)
        if filters.teacher_id:
            query = query.where(AnswerEvaluation.reviewed_by == filters.teacher_id)
        return query

    async def _count(self, query: Select[tuple[AnswerEvaluation]]) -> int:
        count_query = select(func.count()).select_from(query.subquery())
        return (await self.session.execute(count_query)).scalar_one()

    async def get_dashboard_summary(
        self, institution_id: uuid.UUID, filters: TeacherReviewFilters
    ) -> TeacherReviewDashboardSummary:
        base = self._filtered_query(institution_id, filters)
        return TeacherReviewDashboardSummary(
            pending_review_count=await self._count(
                base.where(AnswerEvaluation.review_status == "pending_review")
            ),
            medium_confidence_count=await self._count(
                base.where(AnswerEvaluation.confidence_tier == "medium")
            ),
            low_confidence_count=await self._count(
                base.where(AnswerEvaluation.confidence_tier == "low")
            ),
            completed_reviews_count=await self._count(
                base.where(
                    AnswerEvaluation.review_status.in_(
                        ("teacher_confirmed", "teacher_overridden", "teacher_rejected")
                    )
                )
            ),
            auto_accepted_count=await self._count(
                base.where(AnswerEvaluation.review_status == "auto_suggested")
            ),
        )

    async def get_queue(
        self, institution_id: uuid.UUID, filters: TeacherReviewFilters, params: PageParams
    ) -> tuple[list[AnswerEvaluation], int]:
        query = self._filtered_query(institution_id, filters)
        total = await self._count(query)
        query = query.order_by(AnswerEvaluation.created_at.desc())
        query = query.limit(params.limit).offset(params.offset)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total
