import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { QuestionApproval } from "@/types/assessment";

/**
 * Read-only: `backend/app/api/v1/endpoints/question_approvals.py` exposes
 * only `GET ""` and `GET "/{id}"` — rows are inserted internally by
 * `QuestionApprovalService`, never via a client-facing `POST`, so this is
 * NOT a `createCrudApi` object.
 */
export async function listQuestionApprovals(params?: PageParams): Promise<Page<QuestionApproval>> {
  const { data } = await apiClient.get<Page<QuestionApproval>>("/question-approvals", { params });
  return data;
}

export async function getQuestionApproval(id: string): Promise<QuestionApproval> {
  const { data } = await apiClient.get<QuestionApproval>(`/question-approvals/${id}`);
  return data;
}
