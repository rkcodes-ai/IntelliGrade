import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { QuestionPaperVersion } from "@/types/assessment";

/**
 * Read-only: `backend/app/api/v1/endpoints/question_paper_versions.py`
 * exposes only `GET ""` and `GET "/{id}"` — creation happens exclusively via
 * `createQuestionPaperVersionSnapshot` in `api/questionPapers.ts`
 * (`POST /question-papers/{id}/versions`), so this is NOT a `createCrudApi`
 * object.
 */
export async function listQuestionPaperVersions(
  params?: PageParams,
): Promise<Page<QuestionPaperVersion>> {
  const { data } = await apiClient.get<Page<QuestionPaperVersion>>("/question-paper-versions", {
    params,
  });
  return data;
}

export async function getQuestionPaperVersion(id: string): Promise<QuestionPaperVersion> {
  const { data } = await apiClient.get<QuestionPaperVersion>(`/question-paper-versions/${id}`);
  return data;
}
