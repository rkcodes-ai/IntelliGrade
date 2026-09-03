import { apiClient } from "@/api/client";
import type { AnalyticsFilters, AnalyticsOverview, QuestionWiseAnalytics } from "@/types/teacherReview";

/** Analytics Dashboard (Module 07, Feature 7, ADR-044). See
 * `backend/app/api/v1/endpoints/analytics.py`. */
export async function getAnalyticsOverview(filters?: AnalyticsFilters): Promise<AnalyticsOverview> {
  const { data } = await apiClient.get<AnalyticsOverview>("/analytics/overview", {
    params: filters,
  });
  return data;
}

export async function getQuestionWiseAnalytics(examId: string): Promise<QuestionWiseAnalytics> {
  const { data } = await apiClient.get<QuestionWiseAnalytics>("/analytics/question-wise", {
    params: { exam_id: examId },
  });
  return data;
}
