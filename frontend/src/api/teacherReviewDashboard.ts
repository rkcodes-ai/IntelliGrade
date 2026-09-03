import { apiClient } from "@/api/client";
import type { AnswerEvaluation } from "@/types/officialExam";
import type { Page, PageParams } from "@/types/pagination";
import type { TeacherReviewDashboardSummary, TeacherReviewFilters } from "@/types/teacherReview";

/** Teacher Review Dashboard (Module 07, Feature 1). See
 * `backend/app/api/v1/endpoints/teacher_review_dashboard.py`. */
export async function getTeacherReviewDashboard(
  filters?: TeacherReviewFilters,
): Promise<TeacherReviewDashboardSummary> {
  const { data } = await apiClient.get<TeacherReviewDashboardSummary>(
    "/teacher-review/dashboard",
    { params: filters },
  );
  return data;
}

export async function getTeacherReviewQueue(
  filters?: TeacherReviewFilters,
  params?: PageParams,
): Promise<Page<AnswerEvaluation>> {
  const { data } = await apiClient.get<Page<AnswerEvaluation>>("/teacher-review/queue", {
    params: { ...filters, ...params },
  });
  return data;
}
