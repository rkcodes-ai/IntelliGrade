"""Analytics Dashboard endpoints (Module 07, Feature 7)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.schemas.analytics import AnalyticsFilters, AnalyticsOverview, QuestionWiseAnalytics
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _filters(
    exam_id: uuid.UUID | None = Query(default=None),
    subject_id: uuid.UUID | None = Query(default=None),
    course_id: uuid.UUID | None = Query(default=None),
    department_id: uuid.UUID | None = Query(default=None),
) -> AnalyticsFilters:
    return AnalyticsFilters(
        exam_id=exam_id, subject_id=subject_id, course_id=course_id, department_id=department_id
    )


@router.get(
    "/overview",
    response_model=AnalyticsOverview,
    dependencies=[Depends(require_permissions(PermissionCode.ANALYTICS_READ))],
)
async def get_analytics_overview(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    filters: Annotated[AnalyticsFilters, Depends(_filters)],
) -> AnalyticsOverview:
    service = AnalyticsService(db)
    return await service.get_overview(institution_id, filters)


@router.get(
    "/question-wise",
    response_model=QuestionWiseAnalytics,
    dependencies=[Depends(require_permissions(PermissionCode.ANALYTICS_READ))],
)
async def get_question_wise_analytics(
    exam_id: uuid.UUID,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
) -> QuestionWiseAnalytics:
    service = AnalyticsService(db)
    return await service.get_question_wise(institution_id, exam_id)
