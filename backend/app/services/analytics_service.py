"""Analytics Dashboard (Module 07, Feature 7). See ADR-044.

Every figure is computed on demand from `ExamResult`/`AnswerEvaluation`,
joined through the existing Module 03/04 hierarchy
(`Exam -> Assessment -> Subject -> Course -> Program -> Department`) —
no new persisted rollup table this pass.
"""

import uuid
from collections import Counter, defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer_evaluation import AnswerEvaluation
from app.models.assessment import Assessment
from app.models.assessment_configuration import AssessmentConfiguration
from app.models.course import Course
from app.models.exam import Exam
from app.models.exam_result import ExamResult
from app.models.exam_session import ExamSession
from app.models.extracted_question import ExtractedQuestion
from app.models.program import Program
from app.models.subject import Subject
from app.schemas.analytics import (
    AnalyticsFilters,
    AnalyticsOverview,
    ConfidenceDistribution,
    QuestionPerformance,
    QuestionWiseAnalytics,
)

#: How many entries "most difficult questions" surfaces.
_MOST_DIFFICULT_LIMIT = 5


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _apply_hierarchy_filters(
        self,
        query: Select[Any],
        filters: AnalyticsFilters,
        *,
        exam_col: Any,
        subject_col: Any,
        course_col: Any,
    ) -> Select[Any]:
        if filters.exam_id:
            query = query.where(exam_col == filters.exam_id)
        if filters.subject_id:
            query = query.where(subject_col == filters.subject_id)
        if filters.course_id:
            query = query.where(course_col == filters.course_id)
        return query

    async def _result_rows(self, institution_id: uuid.UUID, filters: AnalyticsFilters) -> Any:
        query = (
            select(
                ExamResult.total_marks,
                ExamResult.total_max_marks,
                AssessmentConfiguration.passing_marks,
                AssessmentConfiguration.maximum_marks,
            )
            .select_from(ExamResult)
            .join(ExamSession, ExamSession.id == ExamResult.exam_session_id)
            .join(Exam, Exam.id == ExamSession.exam_id)
            .join(Assessment, Assessment.id == Exam.assessment_id)
            .join(Subject, Subject.id == Assessment.subject_id)
            .join(Course, Course.id == Subject.course_id)
            .join(Program, Program.id == Course.program_id)
            .outerjoin(
                AssessmentConfiguration, AssessmentConfiguration.assessment_id == Assessment.id
            )
            .where(
                ExamResult.institution_id == institution_id,
                ExamResult.deleted_at.is_(None),
                ExamResult.total_marks.is_not(None),
            )
        )
        query = self._apply_hierarchy_filters(
            query, filters, exam_col=Exam.id, subject_col=Subject.id, course_col=Course.id
        )
        if filters.department_id:
            query = query.where(Program.department_id == filters.department_id)
        return (await self.session.execute(query)).all()

    async def _evaluations_for_scope(
        self, institution_id: uuid.UUID, filters: AnalyticsFilters
    ) -> list[AnswerEvaluation]:
        query = (
            select(AnswerEvaluation)
            .join(ExamSession, ExamSession.id == AnswerEvaluation.exam_session_id)
            .join(Exam, Exam.id == ExamSession.exam_id)
            .join(Assessment, Assessment.id == Exam.assessment_id)
            .join(Subject, Subject.id == Assessment.subject_id)
            .join(Course, Course.id == Subject.course_id)
            .join(Program, Program.id == Course.program_id)
            .where(
                AnswerEvaluation.institution_id == institution_id,
                AnswerEvaluation.deleted_at.is_(None),
            )
        )
        query = self._apply_hierarchy_filters(
            query, filters, exam_col=Exam.id, subject_col=Subject.id, course_col=Course.id
        )
        if filters.department_id:
            query = query.where(Program.department_id == filters.department_id)
        return list((await self.session.execute(query)).scalars().all())

    async def get_overview(
        self, institution_id: uuid.UUID, filters: AnalyticsFilters
    ) -> AnalyticsOverview:
        result_rows = await self._result_rows(institution_id, filters)
        marks = [row.total_marks for row in result_rows]

        pass_count = 0
        fail_count = 0
        determinable = 0
        for row in result_rows:
            if (
                row.passing_marks is not None
                and row.maximum_marks
                and row.maximum_marks > 0
                and row.total_max_marks
                and row.total_max_marks > 0
            ):
                determinable += 1
                achieved_ratio = row.total_marks / row.total_max_marks
                pass_ratio = row.passing_marks / row.maximum_marks
                if achieved_ratio >= pass_ratio:
                    pass_count += 1
                else:
                    fail_count += 1

        evaluations = await self._evaluations_for_scope(institution_id, filters)
        tier_counts = Counter(e.confidence_tier for e in evaluations if e.confidence_tier)
        overridden_count = sum(1 for e in evaluations if e.review_status == "teacher_overridden")
        diffs = [
            abs(e.final_marks - e.suggested_marks)
            for e in evaluations
            if e.final_marks is not None and e.suggested_marks is not None
        ]

        return AnalyticsOverview(
            result_count=len(marks),
            average_marks=(sum(marks, Decimal("0")) / len(marks)) if marks else None,
            highest_marks=max(marks) if marks else None,
            lowest_marks=min(marks) if marks else None,
            pass_percentage=((Decimal(pass_count) / determinable * 100) if determinable else None),
            fail_percentage=((Decimal(fail_count) / determinable * 100) if determinable else None),
            confidence_distribution=ConfidenceDistribution(
                high=tier_counts.get("high", 0),
                medium=tier_counts.get("medium", 0),
                low=tier_counts.get("low", 0),
            ),
            teacher_override_percentage=(
                (Decimal(overridden_count) / len(evaluations) * 100) if evaluations else None
            ),
            average_ai_vs_teacher_difference=(
                (sum(diffs, Decimal("0")) / len(diffs)) if diffs else None
            ),
        )

    async def get_question_wise(
        self, institution_id: uuid.UUID, exam_id: uuid.UUID
    ) -> QuestionWiseAnalytics:
        evaluations = await self._evaluations_for_scope(
            institution_id, AnalyticsFilters(exam_id=exam_id)
        )
        by_question: dict[uuid.UUID, list[AnswerEvaluation]] = defaultdict(list)
        for evaluation in evaluations:
            by_question[evaluation.extracted_question_id].append(evaluation)

        questions: list[QuestionPerformance] = []
        for question_id, question_evals in by_question.items():
            question = await self.session.get(ExtractedQuestion, question_id)
            finals = [e.final_marks for e in question_evals if e.final_marks is not None]
            max_marks = question_evals[0].max_marks
            average_marks = (sum(finals, Decimal("0")) / len(finals)) if finals else None
            average_ratio = (
                (average_marks / max_marks) if average_marks is not None and max_marks else None
            )
            questions.append(
                QuestionPerformance(
                    extracted_question_id=question_id,
                    question_number=question.question_number if question else "",
                    evaluated_count=len(question_evals),
                    max_marks=max_marks,
                    average_marks=average_marks,
                    average_ratio=average_ratio,
                )
            )

        most_difficult = sorted(
            (q for q in questions if q.average_ratio is not None),
            key=lambda q: q.average_ratio,  # type: ignore[arg-type,return-value]
        )[:_MOST_DIFFICULT_LIMIT]

        return QuestionWiseAnalytics(questions=questions, most_difficult=most_difficult)
