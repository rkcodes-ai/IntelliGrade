"""Teacher Review Dashboard endpoints (Module 07, Feature 1)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.answer_evaluation import AnswerEvaluation
from app.schemas.answer_evaluation import AnswerEvaluationRead
from app.schemas.pagination import Page, PageParams
from app.schemas.teacher_review import TeacherReviewDashboardSummary, TeacherReviewFilters
from app.services.teacher_review_dashboard_service import TeacherReviewDashboardService

router = APIRouter(prefix="/teacher-review", tags=["Teacher Review Dashboard"])


def _filters(
    exam_id: uuid.UUID | None = Query(default=None),
    subject_id: uuid.UUID | None = Query(default=None),
    course_id: uuid.UUID | None = Query(default=None),
    department_id: uuid.UUID | None = Query(default=None),
    student_user_id: uuid.UUID | None = Query(default=None),
    confidence_tier: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    teacher_id: uuid.UUID | None = Query(default=None),
) -> TeacherReviewFilters:
    return TeacherReviewFilters(
        exam_id=exam_id,
        subject_id=subject_id,
        course_id=course_id,
        department_id=department_id,
        student_user_id=student_user_id,
        confidence_tier=confidence_tier,
        review_status=review_status,
        teacher_id=teacher_id,
    )


def _to_read(entity: AnswerEvaluation) -> AnswerEvaluationRead:
    return AnswerEvaluationRead.model_validate(entity)


@router.get(
    "/dashboard",
    response_model=TeacherReviewDashboardSummary,
    dependencies=[Depends(require_permissions(PermissionCode.TEACHER_REVIEW_DASHBOARD_READ))],
)
async def get_teacher_review_dashboard(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    filters: Annotated[TeacherReviewFilters, Depends(_filters)],
) -> TeacherReviewDashboardSummary:
    service = TeacherReviewDashboardService(db)
    return await service.get_dashboard_summary(institution_id, filters)


@router.get(
    "/queue",
    response_model=Page[AnswerEvaluationRead],
    dependencies=[Depends(require_permissions(PermissionCode.TEACHER_REVIEW_DASHBOARD_READ))],
)
async def get_teacher_review_queue(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    filters: Annotated[TeacherReviewFilters, Depends(_filters)],
    params: Annotated[PageParams, Depends()],
) -> Page[AnswerEvaluationRead]:
    service = TeacherReviewDashboardService(db)
    items, total = await service.get_queue(institution_id, filters, params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)
